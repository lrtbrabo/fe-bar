# NIP → VPP Copilot — automating ANS complaint resolution for a health insurer

> **The outcome first.** A Brazilian health insurer is fined by the regulator (ANS) whenever it
> fails to resolve a beneficiary complaint (**NIP**) within **5 days**. Today an analyst manually
> hunts, across dozens of a beneficiary's prior-authorization records (**VPPs**), for the one that
> explains the denial — then writes the response by hand. This build **infers the correct VPP the
> moment a NIP arrives, drafts the parecer (the regulator response) grounded in the ANS procedure
> list, and delivers it inside the analyst's workflow** — with a confidence score that, when high
> enough, closes the case end-to-end with no human in the loop.

**Industry:** Health insurance (saúde suplementar, Brazil) · **Regulator:** ANS · **Data:** 100% synthetic.

---

## Why it matters (business value)

| KPI (the buyer's language) | Today | With the copilot |
|---|---|---|
| Avg. NIP handling time | ~25 min (manual VPP hunt + parecer) | **~8 min** (VPP pre-matched, parecer drafted) |
| NIPs resolved within the 5-day ANS deadline | at risk under volume spikes | **SLA countdown + auto-triage** raise on-time rate |
| Duplicated work | 3 analysts can open the same NIP | **inferred once on arrival**, reused |
| Fully automated resolutions | 0% | high-confidence NIPs closed **no-human-in-the-loop** |

**Illustrative impact** — for an insurer receiving ~2,000 NIPs/month, cutting average handling time
from ~25 to ~8 minutes frees **~560 analyst-hours/month**, and every missed 5-day deadline avoided
removes an ANS fine exposure (per-infraction penalties run in the tens of thousands of R$). Numbers
are illustrative estimates on synthetic data, framed for the executive sponsor (cost/risk) and the
domain owner (throughput/quality).

---

## The domain in one picture

```
Beneficiary denied a procedure
        │  (ouvidoria doesn't resolve)
        ▼
   NIP opened at ANS  ──►  5-DAY DEADLINE (fines on delay)
        │
        ▼
Analyst must find the matching VPP (prior-auth guide) among many, then write the parecer
        │
        ▼
   ★ This build: infer VPP + draft parecer automatically, surfaced to the analyst ★
```

**Business rules the matcher must honour (this is the hard part):**
- **pai vs filha** — a complaint about a *procedure* resolves to the **parent** VPP guide; a complaint
  about a *material/medication/OPME* resolves to the **child** manifestação.
- **65-day window** — only prior-authorizations within 65 days of the NIP are candidates.
- **resolved-case status trap** — once a NIP is resolved, the record's status flips (denied→approved),
  so status is *not* a reliable matching signal for historical cases.
- **multi-VPP ambiguity** — a beneficiary with several overlapping guides needs a deterministic tie-break.

---

## Architecture — an integrated end-to-end journey

```
                 (synthetic source exports land in a UC Volume)
                                   │
  ┌────────────┐   ┌───────────────────────────┐   ┌─────────────────────────────┐
  │  LAKEFLOW  │──►│      UNITY CATALOG          │──►│  ML / GEN AI (intelligence) │
  │ Auto Loader│   │ bronze→silver→gold          │   │ • NIP→VPP agent (tools)     │
  │ CSV + JSONL│   │ masking · row filters ·     │   │   + parecer drafting        │
  └────────────┘   │ lineage · grants (LGPD)     │   │ • ANS-rol lookup tool       │
                   └───────────────────────────┘   │ • Vector Search match       │
                                   │                 │ • NIP-propensity ML model   │
                                   ▼                 └─────────────────────────────┘
                        ┌────────────────────┐                    │
                        │      LAKEBASE       │◄───────────────────┘
                        │ operational serving │   match + confidence + parecer + feedback
                        │ (Postgres, low-lat) │
                        └────────────────────┘
                          │                 │
                  ┌───────▼──────┐   ┌───────▼───────────┐
                  │  GENIE AGENT │   │  DATABRICKS APP    │
                  │ NL queries   │   │  (AppKit/React)    │
                  │ for analysts │   │  analyst copilot   │
                  └──────────────┘   └───────────────────┘
```

Each layer feeds the next — raw NIPs/VPPs flow through Lakeflow into governed gold tables, the agent
reads those tables to infer the VPP and draft the parecer, results are served from Lakebase to the
app, and Genie gives analysts a conversational window onto the same governed data.

---

## Repository structure

| Path | What's in it |
|---|---|
| `instructions/` | The FE Bar brief (reference). |
| `01_synthetic_data/` | Deterministic synthetic-data generator + committed samples & summary. |
| `02_lakeflow_pipeline/` | Lakeflow SDP (bronze→silver→gold) SQL transformations. |
| `03_unity_catalog/` | Catalog/schema/volume setup + governance (masking, row filters, tags, grants). |
| `04_intelligence/` | NIP→VPP agent (tool-using) + parecer drafting + NIP-propensity ML model. |
| `05_lakebase/` | Lakebase operational serving (Postgres reverse-ETL loader + analyst write-back). |
| `06_genie/` | Genie Space definition + NL query harness for analysts. |
| `07_app/nip-vpp-copilot/` | Databricks App (AppKit / React): the NIP command center (Painel, Fila, Radar, Agente). |
| `evidence/` | **Execution evidence as text** — run outputs, row counts, model metrics, matcher accuracy. |
| `deck/` | Business presentation (PDF). |

---

## Decisions & trade-offs

- **Tool-using agent over pure `ai_query`** — the pai/filha logic, 65-day window, and resolved-case
  trap are business rules, not prompt trivia. We do **deterministic candidate retrieval** (SQL/UC
  functions) and let the LLM handle fuzzy ranking + parecer drafting. Auditable *and* flexible.
- **Confidence gate for automation** — a real score (not a placeholder) decides human-in-the-loop vs.
  auto-close, so the business controls the risk/automation trade-off.
- **Why Databricks (migration from a BigQuery-agent POC)** — native bidirectional Salesforce
  connector (analysts live in Salesforce), Genie/Databricks One for a no-dev conversational UX, and
  Unity Catalog lineage/governance for regulated health PII.
- **Synthetic data, on purpose hard** — the generator plants pai/filha, the status trap, ambiguity,
  and out-of-window distractors so the matcher is genuinely tested, with a ground-truth oracle.

---

## Live artifacts (deployed on `wks-demo-brabo`, catalog `wks_demo_brabo_catalog`)

| Layer | Artifact | Proof |
|---|---|---|
| Lakeflow | pipeline `nip_vpp_medallion` (18 flows) | [evidence/02](evidence/02_lakeflow_run.md) |
| Unity Catalog | masking + tags on `nip_vpp_silver`/`_gold` | [evidence/03](evidence/03_governance.md) |
| Gen AI | NIP→VPP matcher — **96.6%** on 208 NIPs | [evidence/04](evidence/04_matcher_eval.md) |
| ML | propensity model — ROC-AUC **0.926**, served at `nip-propensity`, batch-scored for the Radar | [evidence/05](evidence/05_ml_propensity.md) |
| Lakebase | Postgres `nip_vpp`: queue, guide explainability, rol check, timeline, radar + 2 write-back tables | [evidence/07](evidence/07_lakebase.md) |
| Genie | space `Agente NIP`, with domain instructions; embedded in the app on behalf of the user | [evidence/06](evidence/06_genie.md) |
| App | `nip-vpp-copilot` (RUNNING) | [evidence/08](evidence/08_app.md) |

Business deck: [`deck/nip-vpp-deck.pdf`](deck/nip-vpp-deck.pdf) · Demo script: [`deck/roleplay-notes.md`](deck/roleplay-notes.md).

## The app: a command center in four moves

| Enxergar (see) | Perguntar (ask) | Resolver (resolve) | Prevenir (prevent) |
|---|---|---|---|
| **Painel**: open backlog by ANS deadline, fine exposure in R$ (editable premise), themes, next best actions | **Agente NIP**: Genie side panel on every screen, context-aware suggestions, runs as the user | **Fila**: inferred VPP with confidence, every discarded guide and why, ANS-rol + plan check, drafted parecer, approve (write-back) | **Radar**: beneficiaries likely to open a NIP, with drivers; the call center acts (write-back) |

![Painel](deck/img/painel.png)
![Fila](deck/img/fila.png)
![Radar](deck/img/radar.png)

## Reproduce it

```bash
# 0) auth: a Databricks CLI profile (this build used `wks-demo-brabo`)
# 1) synthetic data
python3 -m venv .venv && source .venv/bin/activate && pip install faker pandas pyarrow
python 01_synthetic_data/generator/generate.py

# 2) Unity Catalog schemas + landing volume (03_unity_catalog/00_setup_catalog.sql),
#    then upload 01_synthetic_data/output/raw/ to the landing Volume.
# 3) Lakeflow:   databricks bundle deploy && databricks bundle run nip_vpp_pipeline
# 4) Governance: run 03_unity_catalog/01_governance.sql
# 5) Gen AI:     python 04_intelligence/agent/evaluate.py  &&  publish_matches.py
# 6) ML:         python 04_intelligence/ml_propensity/train_propensity.py  &&  score_propensity.py
# 7) Lakebase:   python 05_lakebase/load_lakebase.py   (builds serving tables, loads Postgres, grants the app SP)
# 8) Genie:      python 06_genie/build_space.py   (instructions, sample questions, certified SQL)
# 9) App:        cd 07_app/nip-vpp-copilot && databricks apps deploy
```

---

## Data & privacy

**No real customer data.** Every beneficiary, CPF, plan, TUSS code, procedure, complaint and
call-center transcript is synthesized. TUSS codes are synthetic and do **not** reproduce the real
ANS/TUSS terminology. The scenario is inspired by a real engagement but contains none of its data.

---

*Built as an FE Bar submission. AI was used as a build teammate (Claude Code); the design, decisions,
and narrative are the author's own.*
