# Evidence — Lakeflow pipeline run (bronze → silver → gold)

Pipeline `nip_vpp_medallion` (serverless Lakeflow SDP) deployed via Databricks Asset Bundle and run
with `databricks bundle run nip_vpp_pipeline`. **Update status: COMPLETED.** All 20 flows succeeded
(7 bronze streaming tables via Auto Loader, 6 silver + 5 gold materialized views).

## Flow completion (from the run log)
```
Update d384cd is COMPLETED.
Completed a streaming update of ...bronze_manifestacoes / bronze_procedimentos /
  bronze_dim_beneficiario / bronze_dim_plano / bronze_ref_rol_ans /
  bronze_interacoes_callcenter / bronze_ground_truth
Flow ...silver_manifestacoes / silver_procedimentos / silver_beneficiario /
  silver_plano / silver_rol_ans / silver_callcenter has COMPLETED.
Flow ...gold_vpp_candidatas / gold_nip_queue / gold_beneficiario_360 /
  gold_callcenter_features / gold_eval_ground_truth has COMPLETED.
```

## Row counts (SELECT count(*) per table)
| Table | Rows |
|---|---|
| bronze_manifestacoes | 2585 |
| bronze_procedimentos | 6214 |
| silver_manifestacoes | 2585 |
| silver_procedimentos | 6214 |
| silver_beneficiario | 1500 |
| silver_callcenter | 1828 |
| gold_vpp_candidatas | 2377 |
| gold_nip_queue | 208 |
| gold_beneficiario_360 | 1500 |
| gold_callcenter_features | 1500 |
| gold_eval_ground_truth | 208 |

`gold_vpp_candidatas` = 2377 = 1478 VPP (parent) + 899 VPP_FILHA (child). Counts are consistent
end-to-end (bronze == silver; no rows dropped or exploded).

## Sanity check 1 — NIP queue by SLA status (5-day ANS deadline)
| sla_status | NIPs |
|---|---|
| VENCIDA (overdue) | 115 |
| RESOLVIDA | 80 |
| ATENCAO (≤3 days) | 7 |
| CRITICA (≤1 day) | 6 |

The overdue backlog (115) is exactly the fine-exposure the copilot attacks; 13 active NIPs are inside
the danger zone.

## Sanity check 2 — ML label balance & signal separation (`gold_callcenter_features`)
| abriu_nip | beneficiaries | avg_sentimento | avg_interacoes |
|---|---|---|---|
| 0 (no NIP) | 1292 | +0.144 | 1.04 |
| 1 (opened NIP) | 208 | **−0.294** | **2.34** |

Clear, learnable separation: NIP-openers have markedly more negative call-center sentiment and more
interactions. This is the signal the propensity model will learn.

## Sanity check 3 — `gold_vpp_candidatas` aggregates procedures correctly
VPP_FILHA rows correctly carry the OPME/material line item (e.g. "Stent farmacológico (OPME)",
"Prótese total de joelho (OPME)", "Kit de materiais para videolaparoscopia (OPME)") with
`tem_material_med = 1` — the flag the matcher uses for the pai/filha rule.
