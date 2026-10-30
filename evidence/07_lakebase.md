# Evidence — Lakebase operational serving (Postgres)

Lakebase project `nip-vpp` (Autoscaling, scale-to-zero). `05_lakebase/load_lakebase.py` builds the gold serving tables in Unity Catalog, reverse-ETLs them into Postgres schema `nip_vpp`, and re-grants the app's service principal. The app reads here (low-latency OLTP) and writes decisions back.

## Rows loaded (read-only serving tables)
| Postgres table | Rows |
|---|---|
| `nip_vpp.nip_serving` | 208 |
| `nip_vpp.nip_candidates` | 414 |
| `nip_vpp.nip_rol_check` | 521 |
| `nip_vpp.callcenter` | 1820 |
| `nip_vpp.propensity` | 1500 |

## NIP queue by SLA status (queried live from Lakebase)
| sla_status | NIPs |
|---|---|
| VENCIDA | 106 |
| RESOLVIDA | 88 |
| CRITICA | 6 |
| ATENCAO | 6 |
| NO_PRAZO | 2 |

## Radar: beneficiaries without a NIP, by risk band
| faixa_risco | beneficiaries |
|---|---|
| ALTO | 9 |
| MEDIO | 58 |
| BAIXO | 1225 |

## Write-back tables (kept across loads)
- `nip_vpp.analyst_feedback` — analyst decision per NIP (APROVADO / AJUSTADO / REJEITADO).
- `nip_vpp.retention_actions` — proactive call-center action per at-risk beneficiary.
