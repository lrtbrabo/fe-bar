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
| `05_lakebase/` | Lakebase operational serving + synced tables. |
| `06_genie/` | Genie Space definition for analyst NL queries. |
| `07_app/` | Databricks App (AppKit / React) — the analyst copilot. |
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

## Reproduce it

```bash
# 1) synthetic data
python3 -m venv .venv && source .venv/bin/activate && pip install faker pandas pyarrow
python 01_synthetic_data/generator/generate.py

# 2) Unity Catalog schemas + landing volume, then upload raw data
databricks ... (see 03_unity_catalog/00_setup_catalog.sql)

# 3..7) Lakeflow pipeline, agent, ML model, Lakebase, Genie, App — see each numbered folder.
```

---

## Data & privacy

**No real customer data.** Every beneficiary, CPF, plan, TUSS code, procedure, complaint and
call-center transcript is synthesized. TUSS codes are synthetic and do **not** reproduce the real
ANS/TUSS terminology. The scenario is inspired by a real engagement but contains none of its data.

---

*Built as an FE Bar submission. AI was used as a build teammate (Claude Code); the design, decisions,
and narrative are the author's own.*
