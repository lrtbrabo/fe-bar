"""
Publish the matcher's decisions to a gold table `gold_nip_vpp_matches`.

Mirrors the production design from the customer conversation: the VPP is inferred
when the NIP arrives and the result (match + confidence + drafted parecer) is stored,
so the analyst app just retrieves it instead of re-running inference per view.

Reads the evaluation output (predictions.csv), writes JSONL, lands it in the Volume,
and creates the gold table via read_files. Idempotent.

Usage:  python publish_matches.py
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from dbx_common import CATALOG, PROFILE, query

OUT = Path(__file__).resolve().parent / "output"
VOL = f"/Volumes/{CATALOG}/nip_vpp_bronze/landing/matches"
CONF_THRESHOLD = 0.8


def main():
    rows = list(csv.DictReader(open(OUT / "predictions.csv")))
    recs = []
    for r in rows:
        conf = float(r["confidence"])
        recs.append({
            "nip_id": r["nip_id"],
            "matched_manifestacao_id": r["predicted"],
            "matched_tipo": r["correct_tipo"] if r["predicted"] != "NENHUMA" else "NENHUMA",
            "confidence": conf,
            "auto_resolvavel": conf >= CONF_THRESHOLD,
            "justificativa": r["justificativa"],
            "parecer_sugerido": r["parecer_sugerido"],
            "n_candidatas": int(r["n_candidatas"]),
        })
    jsonl = OUT / "nip_vpp_matches.jsonl"
    with open(jsonl, "w") as f:
        for rec in recs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {len(recs)} match records -> {jsonl}")

    # land in the Volume (ensure the dir exists first)
    subprocess.run(["databricks", "fs", "mkdir", f"dbfs:{VOL}", "-p", PROFILE], check=False)
    subprocess.run(["databricks", "fs", "cp", "--overwrite", str(jsonl),
                    f"dbfs:{VOL}/nip_vpp_matches.jsonl", "-p", PROFILE], check=True)
    print(f"uploaded to {VOL}")

    # (re)create the gold table
    query(f"""
        CREATE OR REPLACE TABLE {CATALOG}.nip_vpp_gold.gold_nip_vpp_matches AS
        SELECT nip_id, matched_manifestacao_id, matched_tipo,
               CAST(confidence AS DOUBLE) AS confidence,
               CAST(auto_resolvavel AS BOOLEAN) AS auto_resolvavel,
               justificativa, parecer_sugerido, CAST(n_candidatas AS INT) AS n_candidatas
        FROM read_files('{VOL}/', format => 'json')
    """)
    query(f"ALTER TABLE {CATALOG}.nip_vpp_gold.gold_nip_vpp_matches "
          f"SET TBLPROPERTIES ('comment' = 'NIP->VPP match results + drafted parecer (inference-on-arrival store).')")
    n = query(f"SELECT count(*) c, sum(CAST(auto_resolvavel AS INT)) auto "
              f"FROM {CATALOG}.nip_vpp_gold.gold_nip_vpp_matches")[0]
    print(f"gold_nip_vpp_matches: {n['c']} rows, {n['auto']} auto-resolvable (conf >= {CONF_THRESHOLD})")


if __name__ == "__main__":
    main()
