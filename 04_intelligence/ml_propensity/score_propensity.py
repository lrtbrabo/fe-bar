"""
Batch-score every beneficiary with the registered NIP-propensity model and publish
gold_propensity_scores — the "radar" of beneficiaries likely to escalate to the ANS
who have NOT opened a NIP yet, with plain-language drivers for the call center.

Scores come from the Unity Catalog model version that is also served at the
`nip-propensity` endpoint. Scores for rows that were in the training split are
in-sample; the honest out-of-sample figures are the test metrics in evidence/05.

Usage:  python score_propensity.py
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import mlflow
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
from dbx_common import CATALOG, PROFILE, query  # noqa: E402

UC_MODEL = f"{CATALOG}.nip_vpp_gold.nip_propensity_model"
MODEL_VERSION = 3
FEATURES = ["n_interacoes", "avg_sentimento", "min_sentimento", "n_interacoes_negativas",
            "total_protocolos", "avg_duracao_seg", "dias_desde_ultima"]
OUT = Path(__file__).resolve().parent / "output"
VOL = f"/Volumes/{CATALOG}/nip_vpp_bronze/landing/propensity_scores"


def faixa(score: float) -> str:
    if score >= 0.7:
        return "ALTO"
    if score >= 0.4:
        return "MEDIO"
    return "BAIXO"


def motivos(r) -> str:
    """Plain-language drivers, ordered by the model's top features (protocols, sentiment)."""
    out = []
    if r["total_protocolos"] >= 2:
        out.append(f"{int(r['total_protocolos'])} protocolos abertos")
    if r["avg_sentimento"] <= -0.2:
        out.append(f"sentimento médio {r['avg_sentimento']:+.2f}".replace(".", ","))
    if r["n_interacoes_negativas"] >= 2:
        out.append(f"{int(r['n_interacoes_negativas'])} contatos negativos")
    if r["n_interacoes"] >= 3:
        out.append(f"{int(r['n_interacoes'])} contatos com o call center")
    return "; ".join(out) or "perfil de contato parecido com o de quem abriu NIP"


def main():
    os.environ["DATABRICKS_CONFIG_PROFILE"] = PROFILE
    mlflow.set_registry_uri("databricks-uc")
    model = mlflow.sklearn.load_model(f"models:/{UC_MODEL}/{MODEL_VERSION}")

    rows = query(f"""
        SELECT f.beneficiario_id, b.nome, b.uf, b.nome_plano, f.abriu_nip, {', '.join('f.' + c for c in FEATURES)}
        FROM {CATALOG}.nip_vpp_gold.gold_callcenter_features f
        JOIN {CATALOG}.nip_vpp_gold.gold_beneficiario_360 b USING (beneficiario_id)""")
    df = pd.DataFrame(rows)
    for c in FEATURES + ["abriu_nip"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["score"] = model.predict_proba(df[FEATURES])[:, 1].round(4)
    df["faixa_risco"] = df["score"].map(faixa)
    df["motivos"] = df.apply(motivos, axis=1)

    OUT.mkdir(exist_ok=True)
    path = OUT / "propensity_scores.csv"
    cols = ["beneficiario_id", "nome", "uf", "nome_plano", "abriu_nip", "score", "faixa_risco",
            "motivos"] + FEATURES
    df[cols].to_csv(path, index=False, quoting=csv.QUOTE_NONNUMERIC)

    subprocess.run(["databricks", "fs", "mkdir", f"dbfs:{VOL}", "-p", PROFILE], check=False)
    subprocess.run(["databricks", "fs", "cp", "--overwrite", str(path),
                    f"dbfs:{VOL}/propensity_scores.csv", "-p", PROFILE], check=True)
    query(f"""
        CREATE OR REPLACE TABLE {CATALOG}.nip_vpp_gold.gold_propensity_scores
        COMMENT 'NIP-propensity score per beneficiary (batch scoring of nip_propensity_model v{MODEL_VERSION}) with drivers.'
        AS SELECT beneficiario_id, nome, uf, nome_plano,
                  CAST(abriu_nip AS INT) AS abriu_nip,
                  CAST(score AS DOUBLE) AS score, faixa_risco, motivos,
                  CAST(n_interacoes AS INT) AS n_interacoes,
                  CAST(avg_sentimento AS DOUBLE) AS avg_sentimento,
                  CAST(n_interacoes_negativas AS INT) AS n_interacoes_negativas,
                  CAST(total_protocolos AS INT) AS total_protocolos,
                  CAST(dias_desde_ultima AS INT) AS dias_desde_ultima
        FROM read_files('{VOL}/', format => 'csv', header => true)""")

    radar = df[df["abriu_nip"] == 0]
    print(f"scored {len(df)} beneficiaries; without NIP: {len(radar)}")
    print(radar["faixa_risco"].value_counts().to_string())
    print(radar.sort_values("score", ascending=False)[["beneficiario_id", "score", "motivos"]].head(5).to_string())


if __name__ == "__main__":
    main()
