# AI Demo Roleplay — prep notes (Part 2)

Two personas in the room: **business stakeholder** (exec who funds it) and **technical stakeholder**
(architect/data lead). Structure everything as **tell → show → tell**, lead with the outcome, switch
altitude per questioner.

## 30-second frame (say this before demoing)
> "SulAmérica-style health insurer. When a beneficiary escalates to the ANS via a NIP, the operator
> has 5 days to respond or it's fined. Analysts hunt manually for the right prior-auth guide (VPP) and
> write the parecer by hand. I built a copilot that infers the VPP the moment the NIP arrives, drafts
> the parecer, and surfaces it in their workflow — with a confidence gate for automation. Let me show you."

## Tell–show–tell for the demo
- **Tell:** "This is the analyst's queue, sorted by how close each NIP is to the 5-day deadline."
- **Show:** open a CRITICA NIP → the complaint, the inferred VPP with a 99% confidence bar, the drafted
  parecer → click Aprovar (write-back). Then the KPI header: 120 open, all auto-resolvable, 98.8% mean confidence.
- **Tell:** "That's ~25 minutes of manual work down to a review-and-approve. At 2,000 NIPs/month that's ~560 analyst-hours back, and fewer blown deadlines = fewer ANS fines."

## Business stakeholder — likely pushback & answers
- **Cost / ROI?** ~560 analyst-hours/month at 2k NIPs; each deadline saved removes a fine exposure (tens of thousands of R$/infraction). Runs on serverless, scales to zero.
- **Risk of wrong answers?** Confidence gate: only high-confidence matches auto-close; the rest stay with a human. 96.6% match accuracy measured against ground truth.
- **Time to value?** The POC already runs; the gap is a data-discovery + pilot with a few analysts. Weeks, not quarters.

## Technical stakeholder — likely pushback & answers
- **Data quality / the tricky rules?** pai vs. filha, the 65-day window, and the resolved-case status
  trap are handled explicitly — deterministic retrieval + rule-aware LLM ranking, evaluated per case type.
- **Governance / LGPD?** Unity Catalog column masking + classification tags; PII stays masked through
  Genie and the app. Full lineage from Volume → bronze → silver → gold.
- **Architecture / integration?** One platform, raw→app: Lakeflow, UC, Lakebase (OLTP serving +
  write-back), Model Serving, Genie, Apps. Native bidirectional Salesforce connector for where analysts work.
- **Why not stay on the BigQuery POC?** Releasing tools to business users was the blocker there; here
  Genie/Databricks One + Apps ship it without exposing dev complexity.

## Altitude switching
When the technical persona goes deep (e.g. "how do you handle the status flip on resolved cases?"),
answer concretely, then re-surface for the exec: "…and the point for the business is the matcher stays
accurate even on historical cases, so we can trust the automation." Keep the demo tight; don't feature-tour.
