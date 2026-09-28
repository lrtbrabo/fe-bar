# Evidence — Lakeflow pipeline run (bronze → silver → gold)

Pipeline `nip_vpp_medallion` (serverless Lakeflow SDP) deployed via Databricks Asset Bundle and run
with `databricks bundle run nip_vpp_pipeline`. **Update status: COMPLETED.** All 18 flows succeeded
(7 bronze streaming tables via Auto Loader, 6 silver + 5 gold materialized views).
Workspace `wks-demo-brabo`, catalog `wks_demo_brabo_catalog`.

## Row counts (SELECT count(*) per table)
| Table | Rows |
|---|---|
| bronze_manifestacoes | 2573 |
| silver_manifestacoes | 2573 |
| silver_procedimentos | 6176 |
| silver_beneficiario | 1500 |
| silver_callcenter | 1820 |
| gold_vpp_candidatas | 2365 |
| gold_nip_queue | 208 |

Counts are consistent end-to-end (bronze == silver; no rows dropped or exploded). `gold_vpp_candidatas`
is the parent+child VPP guides; `gold_nip_queue` is the 208 NIPs.

## NIP queue by SLA status (5-day ANS deadline, anchored to the latest NIP)
| sla_status | NIPs |
|---|---|
| VENCIDA (overdue backlog) | 106 |
| RESOLVIDA (history) | 88 |
| CRITICA (≤1 day) | 6 |
| ATENCAO (≤3 days) | 6 |
| NO_PRAZO | 2 |

The overdue backlog is the fine-exposure the copilot attacks; 14 NIPs are in the active danger zone.

## ML label balance & signal separation (`gold_callcenter_features`)
| abriu_nip | beneficiaries | avg_sentimento | avg_interacoes |
|---|---|---|---|
| 0 (no NIP) | 1292 | +0.139 | 1.02 |
| 1 (opened NIP) | 208 | **−0.311** | **2.42** |

Clear, learnable separation: NIP-openers have markedly more negative call-center sentiment and more
interactions — the signal the propensity model learns.
