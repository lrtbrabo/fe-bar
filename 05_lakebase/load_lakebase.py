"""
Load the Lakebase (Postgres) operational-serving layer for the analyst app.

Reverse-ETL: reads the gold serving table (gold_nip_serving) from Unity Catalog and
writes it into Lakebase Postgres, where the app reads the NIP queue with low latency
and writes analyst decisions back (OLTP). This is the operational-serving tier.

Creates:
  nip_vpp.nip_serving       -- one row per NIP: queue + inferred VPP + drafted parecer
  nip_vpp.analyst_feedback  -- write-back: analyst decision per NIP (app writes here)

Usage:  python load_lakebase.py
"""
from __future__ import annotations

import json
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

COLS = ["nip_id", "beneficiario_id", "beneficiario_nome", "plano_id", "nome_plano",
        "reclamacao_texto", "data_criacao", "prazo_ans", "dias_para_prazo", "sla_status",
        "status", "resolvida", "vpp_citada", "matched_manifestacao_id", "matched_tipo",
        "confidence", "auto_resolvavel", "justificativa", "parecer_sugerido"]

DDL = """
CREATE SCHEMA IF NOT EXISTS nip_vpp;
DROP TABLE IF EXISTS nip_vpp.nip_serving;
CREATE TABLE nip_vpp.nip_serving (
  nip_id                  text PRIMARY KEY,
  beneficiario_id         text,
  beneficiario_nome       text,
  plano_id                text,
  nome_plano              text,
  reclamacao_texto        text,
  data_criacao            timestamp,
  prazo_ans               timestamp,
  dias_para_prazo         int,
  sla_status              text,
  status                  text,
  resolvida               boolean,
  vpp_citada              text,
  matched_manifestacao_id text,
  matched_tipo            text,
  confidence              double precision,
  auto_resolvavel         boolean,
  justificativa           text,
  parecer_sugerido        text
);
CREATE INDEX IF NOT EXISTS idx_nip_sla ON nip_vpp.nip_serving (sla_status, dias_para_prazo);

CREATE TABLE IF NOT EXISTS nip_vpp.analyst_feedback (
  feedback_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nip_id        text NOT NULL,
  decisao       text NOT NULL,          -- APROVADO | AJUSTADO | REJEITADO
  parecer_final text,
  analista      text,
  criado_em     timestamp DEFAULT now()
);
"""


def conn_kwargs():
    host = subprocess.check_output(
        ["databricks", "postgres", "get-endpoint", ENDPOINT, "-p", PROFILE, "-o", "json"], text=True)
    host = json.loads(host)["status"]["hosts"]["host"]
    token = subprocess.check_output(
        ["databricks", "postgres", "generate-database-credential", ENDPOINT, "-p", PROFILE, "-o", "json"],
        text=True)
    token = json.loads(token)["token"]
    # macOS: pass hostaddr to dodge getaddrinfo issues, keep host for TLS SNI
    ip = socket.gethostbyname(host)
    return dict(host=host, hostaddr=ip, dbname=PG_DB, user=PG_USER, password=token, sslmode="require")


def main():
    rows = query(f"SELECT {', '.join(COLS)} FROM {CATALOG}.nip_vpp_gold.gold_nip_serving")
    print(f"read {len(rows)} rows from gold_nip_serving")

    with psycopg.connect(**conn_kwargs()) as conn, conn.cursor() as cur:
        cur.execute(DDL)
        placeholders = ", ".join(["%s"] * len(COLS))
        data = [tuple(r[c] for c in COLS) for r in rows]
        cur.executemany(
            f"INSERT INTO nip_vpp.nip_serving ({', '.join(COLS)}) VALUES ({placeholders})", data)
        conn.commit()

        cur.execute("SELECT count(*) FROM nip_vpp.nip_serving")
        total = cur.fetchone()[0]
        cur.execute("SELECT sla_status, count(*) FROM nip_vpp.nip_serving GROUP BY sla_status ORDER BY 2 DESC")
        sla = cur.fetchall()
        cur.execute("SELECT count(*) FROM nip_vpp.nip_serving WHERE auto_resolvavel")
        auto = cur.fetchone()[0]

    lines = ["# Evidence — Lakebase operational serving (Postgres)\n",
             f"Lakebase project `nip-vpp` (Autoscaling, scale-to-zero). Reverse-ETL loaded "
             f"`gold_nip_serving` -> Postgres `nip_vpp.nip_serving`; the app reads the queue here "
             f"(low-latency OLTP) and writes analyst decisions to `nip_vpp.analyst_feedback`.\n",
             f"**Loaded {total} NIPs** into `nip_vpp.nip_serving`. {auto} are auto-resolvable "
             f"(confidence >= 0.8).\n",
             "## Rows by SLA status (queried live from Lakebase Postgres)",
             "| sla_status | NIPs |", "|---|---|"]
    lines += [f"| {s} | {n} |" for s, n in sla]
    lines += ["\n## Tables", "- `nip_vpp.nip_serving` — PK `nip_id`, index on `(sla_status, dias_para_prazo)`.",
              "- `nip_vpp.analyst_feedback` — write-back of analyst decisions (APROVADO/AJUSTADO/REJEITADO)."]
    report = "\n".join(lines) + "\n"
    (Path(__file__).resolve().parents[1] / "evidence" / "07_lakebase.md").write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    main()
