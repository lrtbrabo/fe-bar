# Evidence — Databricks App (AppKit / React analyst copilot)

App **`nip-vpp-copilot`** (AppKit, TypeScript/React + Express) deployed to Databricks Apps.
**Status: RUNNING.** URL: `https://nip-vpp-copilot-7474652430122624.aws.databricksapps.com`

Reads the NIP queue from Lakebase Postgres (`nip_vpp.nip_serving`, low-latency OLTP) and writes
analyst decisions back to `nip_vpp.analyst_feedback`. The app's service principal
(`2c8db49d-1162-4ef7-9527-9346d25c6267`) was granted USAGE/SELECT on the schema and INSERT on the
feedback table.

## `GET /api/kpis` (live, from Lakebase)
```json
{"sla":[{"sla_status":"VENCIDA","n":106},{"sla_status":"CRITICA","n":6},{"sla_status":"ATENCAO","n":6},
        {"sla_status":"NO_PRAZO","n":2},{"sla_status":"RESOLVIDA","n":88}],
 "agg":{"total":208,"abertas":120,"auto_abertas":120,"conf_media":"0.988"}}
```

## `GET /api/nips?sla=CRITICA` (6 rows; note the PII masking flows through to the app)
```json
{"nip_id":"MAN-0000093","beneficiario_nome":"Melina R.","nome_plano":"Saúde Total Nacional",
 "sla_status":"CRITICA","dias_para_prazo":0,
 "reclamacao_texto":"Estou revoltado. Pedi autorização para consulta com o ortopedista ...",
 "matched_manifestacao_id":"...", "confidence":0.99, "auto_resolvavel":true, ...}
```

## `POST /api/nips/MAN-0000093/feedback` → write-back to Lakebase
```json
request : {"decisao":"APROVADO","parecer_final":"...","analista":"lucas.brabo"}
response: {"feedback_id":"1","nip_id":"MAN-0000093","decisao":"APROVADO","criado_em":"2026-09-28T17:27:22.812Z"}
```
`GET /api/feedback` then returns the persisted decision — the operational write-back round-trips.

## What the analyst sees
- KPI header: open NIPs, auto-resolvable count, mean confidence, overdue backlog, total.
- Queue filterable by SLA status (ATIVAS / CRITICA / ATENCAO / VENCIDA / RESOLVIDA / TODAS),
  most-urgent-first, with a semantic SLA badge per row.
- Detail panel per NIP: the complaint, the **inferred VPP** (id + tipo + confidence bar +
  auto-resolvable badge + justificativa), and the **drafted parecer** in an editable box with
  Aprovar / Salvar ajuste / Rejeitar actions that persist to Lakebase.
