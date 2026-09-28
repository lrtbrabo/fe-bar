"""
Evaluate the NIP->VPP matcher against the ground-truth oracle.

Bulk-fetches the gold tables, runs the matcher on every NIP (deterministic 65-day
candidate retrieval + LLM rule-aware ranking), compares to ground truth, and writes
an accuracy report broken down by the planted hard-case types.

Usage:  python evaluate.py [--limit N] [--workers K] [--model NAME]
"""
from __future__ import annotations

import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from dbx_common import CATALOG, query
from matcher import WINDOW_DAYS, match_nip

EVID = Path(__file__).resolve().parents[2] / "evidence"
OUT = Path(__file__).resolve().parent / "output"


def fetch():
    nips = query(f"""SELECT nip_id, beneficiario_id, reclamacao_texto, data_criacao,
                            vpp_citada, resolvida
                     FROM {CATALOG}.nip_vpp_gold.gold_nip_queue""")
    cands = query(f"""SELECT manifestacao_id, beneficiario_id, tipo, manifestacao_pai_id,
                             vpp_numero, data_criacao, status, descricao, n_itens,
                             tem_material_med, procedimentos_texto
                      FROM {CATALOG}.nip_vpp_gold.gold_vpp_candidatas""")
    gt = {g["nip_id"]: g for g in
          query(f"SELECT * FROM {CATALOG}.nip_vpp_gold.gold_eval_ground_truth")}
    return nips, cands, gt


def index_candidates(cands):
    by_ben: dict[str, list] = {}
    for c in cands:
        by_ben.setdefault(c["beneficiario_id"], []).append(c)
    return by_ben


def candidates_in_window(nip, by_ben):
    lo = nip["data_criacao"] - timedelta(days=WINDOW_DAYS)
    hi = nip["data_criacao"]
    return [c for c in by_ben.get(nip["beneficiario_id"], [])
            if lo <= c["data_criacao"] <= hi]


def evaluate_one(nip, by_ben, gt, model):
    cands = candidates_in_window(nip, by_ben)
    dec = match_nip(nip, cands, model=model)
    truth = gt[nip["nip_id"]]
    correct = dec["chosen_manifestacao_id"] == truth["correct_manifestacao_id"]
    return {
        "nip_id": nip["nip_id"],
        "predicted": dec["chosen_manifestacao_id"],
        "expected": truth["correct_manifestacao_id"],
        "correct": int(correct),
        "confidence": round(dec["confidence"], 3),
        "complaint_type": truth["complaint_type"],
        "correct_tipo": truth["correct_tipo"],
        "nip_resolvida": int(truth["nip_resolvida"]),
        "ambigua": int(truth["ambigua"]),
        "fora_janela": int(truth["tem_distrator_fora_janela"]),
        "cita_vpp": int(truth["cita_vpp"]),
        "n_candidatas": len(cands),
        "justificativa": dec.get("justificativa", ""),
        "parecer_sugerido": dec.get("parecer_sugerido", ""),
    }


def acc(rows):
    return (sum(r["correct"] for r in rows) / len(rows)) if rows else 0.0


def segment(rows, key, val):
    return [r for r in rows if r[key] == val]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    nips, cands, gt = fetch()
    if args.limit:
        nips = nips[:args.limit]
    by_ben = index_candidates(cands)
    print(f"Evaluating {len(nips)} NIPs against {len(cands)} candidate guides...")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(evaluate_one, n, by_ben, gt, args.model) for n in nips]
        for i, f in enumerate(futs, 1):
            results.append(f.result())
            if i % 25 == 0:
                print(f"  {i}/{len(nips)}")

    overall = acc(results)
    high = [r for r in results if r["confidence"] >= 0.8]
    low = [r for r in results if r["confidence"] < 0.8]

    segs = [
        ("Complaint -> PARENT guide (pai)",  segment(results, "correct_tipo", "VPP")),
        ("Complaint -> CHILD (filha)",       segment(results, "correct_tipo", "VPP_FILHA")),
        ("Resolved NIPs (status trap)",      segment(results, "nip_resolvida", 1)),
        ("Unresolved NIPs",                  segment(results, "nip_resolvida", 0)),
        ("Multi-VPP ambiguity",              segment(results, "ambigua", 1)),
        ("Has out-of-window distractor",     segment(results, "fora_janela", 1)),
        ("Beneficiary cited the VPP number", segment(results, "cita_vpp", 1)),
    ]

    lines = []
    lines.append("# Evidence — NIP->VPP matcher accuracy\n")
    lines.append(f"Model: `{args.model or 'databricks-gpt-6-sol'}` (Databricks Foundation Model API). "
                 f"Deterministic 65-day + beneficiary retrieval, LLM rule-aware ranking.\n")
    lines.append(f"**Overall accuracy: {overall:.1%}** on {len(results)} NIPs "
                 f"(exact manifestação-id match vs. ground truth).\n")
    lines.append("## Accuracy by planted hard-case type")
    lines.append("| Segment | N | Accuracy |")
    lines.append("|---|---|---|")
    for name, rows in segs:
        if rows:
            lines.append(f"| {name} | {len(rows)} | {acc(rows):.1%} |")
    lines.append("\n## Confidence calibration")
    lines.append("| Confidence band | N | Accuracy |")
    lines.append("|---|---|---|")
    if high:
        lines.append(f"| high (>= 0.8) | {len(high)} | {acc(high):.1%} |")
    if low:
        lines.append(f"| low (< 0.8) | {len(low)} | {acc(low):.1%} |")
    lines.append("\n> The confidence gate is what enables safe automation: high-confidence matches "
                 "can auto-close; low-confidence ones stay with a human.\n")

    # a few worked examples
    lines.append("## Sample decisions (with drafted parecer)")
    for r in [x for x in results if x["correct"]][:2] + [x for x in results if not x["correct"]][:1]:
        verdict = "correct" if r["correct"] else "MISS"
        lines.append(f"\n**{r['nip_id']}** — {verdict} · conf {r['confidence']} · "
                     f"pred `{r['predicted']}` vs exp `{r['expected']}` ({r['complaint_type']})")
        lines.append(f"- justificativa: {r['justificativa']}")
        if r["parecer_sugerido"]:
            lines.append(f"- parecer sugerido: {r['parecer_sugerido'][:280]}")

    report = "\n".join(lines) + "\n"
    EVID.mkdir(exist_ok=True)
    (EVID / "04_matcher_eval.md").write_text(report, encoding="utf-8")

    OUT.mkdir(exist_ok=True)
    with open(OUT / "predictions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    print("\n" + report)
    print(f"Wrote {EVID/'04_matcher_eval.md'} and {OUT/'predictions.csv'}")


if __name__ == "__main__":
    main()
