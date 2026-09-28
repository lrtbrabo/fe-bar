# Evidence — Lakebase operational serving (Postgres)

Lakebase project `nip-vpp` (Autoscaling, scale-to-zero). Reverse-ETL loaded `gold_nip_serving` -> Postgres `nip_vpp.nip_serving`; the app reads the queue here (low-latency OLTP) and writes analyst decisions to `nip_vpp.analyst_feedback`.

**Loaded 208 NIPs** into `nip_vpp.nip_serving`. 208 are auto-resolvable (confidence >= 0.8).

## Rows by SLA status (queried live from Lakebase Postgres)
| sla_status | NIPs |
|---|---|
| VENCIDA | 106 |
| RESOLVIDA | 88 |
| CRITICA | 6 |
| ATENCAO | 6 |
| NO_PRAZO | 2 |

## Tables
- `nip_vpp.nip_serving` — PK `nip_id`, index on `(sla_status, dias_para_prazo)`.
- `nip_vpp.analyst_feedback` — write-back of analyst decisions (APROVADO/AJUSTADO/REJEITADO).
