# Evidence — Databricks App (AppKit / React): the NIP command center

App **`nip-vpp-copilot`** (AppKit 0.57, TypeScript/React + Express) deployed to Databricks Apps.
**Status: RUNNING / compute ACTIVE.** URL: `https://nip-vpp-copilot-7474652430122624.aws.databricksapps.com`

App resources (from `databricks apps get`): `postgres` (Lakebase project `nip-vpp`, CAN_CONNECT_AND_CREATE)
and `genie-space` (CAN_RUN). User API scope: `dashboards.genie`, so the embedded agent runs **on behalf
of the signed-in user** and Unity Catalog masking applies to its answers.

## Screens

| Screen | Question it answers | Reads | Writes |
|---|---|---|---|
| **Painel** | How is the queue and what does it cost? | `nip_vpp.nip_serving`, `propensity`, write-back tables | — |
| **Fila de NIPs** | Which guide, why, does the rol cover it, what is the parecer? | `nip_serving`, `nip_candidates`, `nip_rol_check`, `callcenter` | `analyst_feedback` |
| **Radar de prevenção** | Who will open a NIP next? | `propensity` | `retention_actions` |
| **Agente NIP** (side panel, every screen) | Anything else, in Portuguese | Genie space over the gold tables (OBO) | — |

Screenshots for humans: `deck/img/painel.png`, `fila.png`, `agente.png`, `radar.png` (not execution evidence).

## Live API checks against the deployed app (HTTP 200 for every route)
```
GET /api/overview          200 1530B
GET /api/nips?sla=CRITICA  200 3241B
GET /api/nips/MAN-0000093  200 4117B
GET /api/radar?faixa=RISCO 200 21145B
GET /api/activity          200  359B
```

### `GET /api/overview` (Painel)
```json
"totals": {"total": 208, "abertas": 120, "prontas": 120, "vencidas": 106, "criticas": 6, "conf_media": 0.987}
"radar":  {"alto": 9, "medio": 58, "acionados": 0}
"temas" (top 3): stent no coração 20 abertas / 19 vencidas · hemodiálise 19 / 16 · parto 16 / 13
"weekly" (last 3): 07/09 9 abertas + 10 resolvidas · 14/09 18 + 13 · 21/09 8 + 10
```
With the default illustrative premise (R$ 30 mil per overdue NIP, editable on screen) the Painel shows
**R$ 3,2 mi** of fine exposure and **34 h** of analyst time the copilot returns on the current backlog.

### `GET /api/nips/MAN-0002164` (Fila: the demo NIP)
```
complaint : "Reclamo da demora na liberação do banda gástrica para o meu cirurgia bariátrica.
             A guia da cirurgia saiu, só falta o material, e o hospital não marca sem ele."
matched   : VPP0001234 · VPP_FILHA · confidence 0.99
candidates: VPP0001234 VPP_FILHA 08/09  Escolhida pelo agente
            VPP0001234 VPP       07/09  Guia pai: a reclamação é sobre o item (regra pai/filha)
            VPP0001232 VPP       22/08  Procedimentos não correspondem à reclamação
            VPP0001233 VPP       06/05  Fora da janela de 65 dias
rol check : Banda gástrica ajustável (OPME) · NEGADO · no rol: true · plano cobre: true
            -> UI suggestion: "reverter a negativa"
timeline  : 06/05 guia · 02/08 contato (sentimento -0,36) · 04/08 contato (-0,51) ·
            22/08 guia · 07/09 guia · 08/09 item · 20/09 NIP aberta na ANS
```
All three hard matcher rules (pai/filha, procedure fit, 65-day window) are visible and explained in one screen.

### `GET /api/radar?faixa=ALTO` (Radar)
```
9 beneficiaries without a NIP in the high-risk band, e.g.
BEN-001396 0.81  2 protocolos abertos; sentimento médio -0,23
BEN-000273 0.80  3 protocolos abertos; 2 contatos negativos; 5 contatos com o call center
BEN-000771 0.79  sentimento médio -0,40
```

### Write-back round-trips (Lakebase)
```
POST /api/nips/:id/feedback {"decisao":"APROVADO"}  -> 201, row in nip_vpp.analyst_feedback
POST /api/radar/BEN-001396/acao {"acao":"LIGAR"}    -> 201 {"acao_id":"1","acao":"LIGAR",...}
GET  /api/radar?faixa=ALTO                          -> BEN-001396 ultima_acao=LIGAR acionado_em=30/10 16:13
POST /api/radar/BEN-001396/acao {"acao":"X"}        -> 400 (zod validation)
```
(The radar test row was deleted afterwards so the demo starts clean; `05_lakebase/reset_demo.sql` resets both write-back tables.)

### Agent inside the app (`POST /api/genie/default/messages`, SSE, on behalf of the user)
```
Q: Quantos beneficiários estão em risco alto de abrir NIP e por quê?
events: message_start · status ×5 · message_result · query_result
A: "Há 9 beneficiários em risco alto de abrir NIP. Os motivos identificados foram: protocolos abertos,
    contatos negativos e sentimento médio negativo no call center…"
```
More agent Q&A (with the generated SQL) in `evidence/06_genie.md`.

## Validation
`databricks apps validate`: types generated, AST-grep lint, type check, build and tests all passed.
A browser run (Playwright, Chromium) drove Painel → Fila crítica → agent → Radar with **zero console errors**.
