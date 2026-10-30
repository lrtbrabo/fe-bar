"""
Load the Lakebase (Postgres) operational-serving layer for the analyst app.

1. Builds the gold serving tables in Unity Catalog (01_build_serving.sql).
2. Reverse-ETL: copies them into Lakebase Postgres (schema nip_vpp), where the app
   reads with low latency and writes analyst / call-center decisions back (OLTP).
3. Re-grants the app's service principal (re-creating a table drops its grants).

Read-only serving tables (rebuilt every run):
  nip_vpp.nip_serving      one row per NIP: queue + inferred VPP + parecer + tema
  nip_vpp.nip_candidates   every prior guide per NIP + why it was (not) chosen
  nip_vpp.nip_rol_check    items of the matched guide vs. ANS rol + plan segmentation
  nip_vpp.callcenter       call-center interactions (beneficiary timeline)
  nip_vpp.propensity       NIP-propensity score per beneficiary (radar)
Write-back tables (kept across runs):
  nip_vpp.analyst_feedback   analyst decision per NIP
  nip_vpp.retention_actions  proactive call-center action per at-risk beneficiary

Usage:  python load_lakebase.py
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "04_intelligence" / "agent"))
from dbx_common import CATALOG, PROFILE, query  # noqa: E402

ENDPOINT = "projects/nip-vpp/branches/production/endpoints/primary"
PG_USER = "lucas.brabo@databricks.com"
PG_DB = "databricks_postgres"
APP_NAME = "nip-vpp-copilot"
GOLD = f"{CATALOG}.nip_vpp_gold"
SILVER = f"{CATALOG}.nip_vpp_silver"

# (postgres table, source SELECT on Unity Catalog, Postgres DDL body, extra index DDL)
SERVING = [
    ("nip_serving",
     f"""SELECT nip_id, beneficiario_id, beneficiario_nome, plano_id, nome_plano, plano_segmentacao,
                reclamacao_texto, data_criacao, prazo_ans, dias_para_prazo, sla_status, status, resolvida,
                vpp_citada, matched_manifestacao_id, matched_tipo, matched_vpp_numero, confidence,
                auto_resolvavel, justificativa, parecer_sugerido, tema, categoria_reclamacao
         FROM {GOLD}.gold_nip_serving""",
     """nip_id text PRIMARY KEY, beneficiario_id text, beneficiario_nome text, plano_id text,
        nome_plano text, plano_segmentacao text, reclamacao_texto text, data_criacao timestamp,
        prazo_ans timestamp, dias_para_prazo int, sla_status text, status text, resolvida boolean,
        vpp_citada text, matched_manifestacao_id text, matched_tipo text, matched_vpp_numero text,
        confidence double precision, auto_resolvavel boolean, justificativa text,
        parecer_sugerido text, tema text, categoria_reclamacao text""",
     ["CREATE INDEX ON nip_vpp.nip_serving (sla_status, dias_para_prazo)",
      "CREATE INDEX ON nip_vpp.nip_serving (beneficiario_id)"]),
    ("nip_candidates",
     f"""SELECT nip_id, manifestacao_id, tipo, vpp_numero, data_criacao, status, procedimentos_texto,
                dias_antes_nip, dentro_janela, escolhida, motivo
         FROM {GOLD}.gold_nip_candidatas_avaliadas""",
     """nip_id text, manifestacao_id text, tipo text, vpp_numero text, data_criacao timestamp,
        status text, procedimentos_texto text, dias_antes_nip int, dentro_janela boolean,
        escolhida boolean, motivo text, PRIMARY KEY (nip_id, manifestacao_id)""",
     []),
    ("nip_rol_check",
     f"""SELECT nip_id, codigo_tuss, descricao_procedimento, tipo_item, status_item, no_rol,
                segmentacao_cobertura, plano_segmentacao, segmentacao_cobre, dut_texto
         FROM {GOLD}.gold_nip_rol_check""",
     """nip_id text, codigo_tuss text, descricao_procedimento text, tipo_item text, status_item text,
        no_rol boolean, segmentacao_cobertura text, plano_segmentacao text,
        segmentacao_cobre boolean, dut_texto text""",
     ["CREATE INDEX ON nip_vpp.nip_rol_check (nip_id)"]),
    ("callcenter",
     f"""SELECT interacao_id, beneficiario_id, data_interacao, canal, assunto, sentimento_score,
                transcricao, protocolos_abertos
         FROM {SILVER}.silver_callcenter""",
     """interacao_id text PRIMARY KEY, beneficiario_id text, data_interacao timestamp, canal text,
        assunto text, sentimento_score double precision, transcricao text, protocolos_abertos int""",
     ["CREATE INDEX ON nip_vpp.callcenter (beneficiario_id, data_interacao)"]),
    ("propensity",
     f"""SELECT beneficiario_id, nome, uf, nome_plano, abriu_nip, score, faixa_risco, motivos,
                n_interacoes, avg_sentimento, n_interacoes_negativas, total_protocolos, dias_desde_ultima
         FROM {GOLD}.gold_propensity_scores""",
     """beneficiario_id text PRIMARY KEY, nome text, uf text, nome_plano text, abriu_nip int,
        score double precision, faixa_risco text, motivos text, n_interacoes int,
        avg_sentimento double precision, n_interacoes_negativas int, total_protocolos int,
        dias_desde_ultima int""",
     ["CREATE INDEX ON nip_vpp.propensity (abriu_nip, score DESC)"]),
]

WRITE_BACK = """
CREATE TABLE IF NOT EXISTS nip_vpp.analyst_feedback (
  feedback_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nip_id        text NOT NULL,
  decisao       text NOT NULL,          -- APROVADO | AJUSTADO | REJEITADO
  parecer_final text,
  analista      text,
  criado_em     timestamp DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_feedback_nip ON nip_vpp.analyst_feedback (nip_id, criado_em DESC);
CREATE TABLE IF NOT EXISTS nip_vpp.retention_actions (
  acao_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  beneficiario_id text NOT NULL,
  acao            text NOT NULL,        -- LIGAR | PRIORIZAR_AUTORIZACAO | OUVIDORIA_PROATIVA
  analista        text,
  criado_em       timestamp DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_retention_ben ON nip_vpp.retention_actions (beneficiario_id, criado_em DESC);
"""


def build_gold():
    sql = (Path(__file__).parent / "01_build_serving.sql").read_text()
    sql = re.sub(r"--[^\n]*", "", sql)
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        query(stmt)
    print("built gold serving tables")


def conn_kwargs():
    ep = json.loads(subprocess.check_output(
        ["databricks", "postgres", "get-endpoint", ENDPOINT, "-p", PROFILE, "-o", "json"], text=True))
    host = ep["status"]["hosts"]["host"]
    token = json.loads(subprocess.check_output(
        ["databricks", "postgres", "generate-database-credential", ENDPOINT, "-p", PROFILE, "-o", "json"],
        text=True))["token"]
    # macOS: pass hostaddr to dodge getaddrinfo issues, keep host for TLS SNI
    return dict(host=host, hostaddr=socket.gethostbyname(host), dbname=PG_DB, user=PG_USER,
                password=token, sslmode="require")


def app_sp() -> str:
    app = json.loads(subprocess.check_output(
        ["databricks", "apps", "get", APP_NAME, "-p", PROFILE, "-o", "json"], text=True))
    return app["service_principal_client_id"]


def main():
    build_gold()
    sp = app_sp()
    counts = {}
    with psycopg.connect(**conn_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS nip_vpp")
        for table, select, ddl, indexes in SERVING:
            rows = query(select)
            cols = [c.split()[0] for c in re.split(r",\s*(?![^()]*\))", ddl)
                    if c.strip() and not c.strip().startswith("PRIMARY KEY")]
            cur.execute(f"DROP TABLE IF EXISTS nip_vpp.{table}")
            cur.execute(f"CREATE TABLE nip_vpp.{table} ({ddl})")
            for idx in indexes:
                cur.execute(idx)
            ph = ", ".join(["%s"] * len(cols))
            cur.executemany(f"INSERT INTO nip_vpp.{table} ({', '.join(cols)}) VALUES ({ph})",
                            [tuple(r[c] for c in cols) for r in rows])
            counts[table] = len(rows)
        cur.execute(WRITE_BACK)
        cur.execute(f'GRANT USAGE ON SCHEMA nip_vpp TO "{sp}"')
        cur.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA nip_vpp TO "{sp}"')
        cur.execute(f'GRANT INSERT ON nip_vpp.analyst_feedback, nip_vpp.retention_actions TO "{sp}"')
        cur.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA nip_vpp TO "{sp}"')
        cur.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA nip_vpp GRANT SELECT ON TABLES TO "{sp}"')
        conn.commit()

        cur.execute("SELECT sla_status, count(*) FROM nip_vpp.nip_serving GROUP BY 1 ORDER BY 2 DESC")
        sla = cur.fetchall()
        cur.execute("SELECT faixa_risco, count(*) FROM nip_vpp.propensity WHERE abriu_nip = 0 GROUP BY 1 ORDER BY 2")
        radar = cur.fetchall()

    lines = ["# Evidence — Lakebase operational serving (Postgres)\n",
             "Lakebase project `nip-vpp` (Autoscaling, scale-to-zero). `05_lakebase/load_lakebase.py` "
             "builds the gold serving tables in Unity Catalog, reverse-ETLs them into Postgres schema "
             "`nip_vpp`, and re-grants the app's service principal. The app reads here (low-latency OLTP) "
             "and writes decisions back.\n",
             "## Rows loaded (read-only serving tables)", "| Postgres table | Rows |", "|---|---|"]
    lines += [f"| `nip_vpp.{t}` | {n} |" for t, n in counts.items()]
    lines += ["\n## NIP queue by SLA status (queried live from Lakebase)", "| sla_status | NIPs |", "|---|---|"]
    lines += [f"| {s} | {n} |" for s, n in sla]
    lines += ["\n## Radar: beneficiaries without a NIP, by risk band", "| faixa_risco | beneficiaries |",
              "|---|---|"]
    lines += [f"| {f} | {n} |" for f, n in radar]
    lines += ["\n## Write-back tables (kept across loads)",
              "- `nip_vpp.analyst_feedback` — analyst decision per NIP (APROVADO / AJUSTADO / REJEITADO).",
              "- `nip_vpp.retention_actions` — proactive call-center action per at-risk beneficiary."]
    report = "\n".join(lines) + "\n"
    (Path(__file__).resolve().parents[1] / "evidence" / "07_lakebase.md").write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    main()
