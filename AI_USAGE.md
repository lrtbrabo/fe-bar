# How AI was used: a teammate with tools, evals and guardrails

This build came out of one long-running **Claude Code** session (2026-09-25 → 2026-11-03):
**12 prompts from the author** steered **~430 agent tool calls** (shell, Databricks CLI, file edits,
MCP servers) and 16 commits. The author chose the problem, locked the four design decisions and kept
every irreversible action; the agent proposed, built, tested and fixed. This page documents the
tools, the prompts and the patterns, what went wrong, and where AI usage goes next.

---

## 1. Toolchain

| Tool | Role in this build |
|---|---|
| **Claude Code** (Opus) | The agent, in the terminal: planned, wrote all the code, ran every command, read the errors and iterated. |
| **Databricks CLI + Asset Bundles** | The agent's hands on the platform: pipeline deploy and runs, SQL, Lakebase, Genie, Model Serving, Apps. |
| **Agent skills** (playbooks loaded on demand) | `databricks`, `databricks-spark-declarative-pipelines`, `databricks-lakebase`, `databricks-genie` and `databricks-apps`, one per layer; `dataviz` for the app charts; `google-slides` and `google-auth` for the deck; `markdown-to-pdf` for the markdown deck. |
| **MCP server: Plaud** | Read the discovery-call transcript and summary that the business rules came from. |
| **Playwright + headless Chromium** | The agent drove the app UI itself and checked for console errors. |
| **Foundation Model API** (`databricks-gpt-6-sol`) | AI inside the product: the NIP → VPP matcher and the parecer draft. |

## 2. The prompts that steered the build

The author's prompts are short. The leverage comes from the context the agent could reach (the
`instructions/` brief, the call transcript, memory files) and from the agent checking its own work.
Condensed and translated from Portuguese, customer name removed:

| Prompt | What it set in motion |
|---|---|
| "Look at the instructions folder and tell me what you understood. Don't build anything yet." | The rubric summarized and agreed on before any code. |
| "Think NIP and VPP for health insurers. I discussed this exact use case with a customer yesterday; look at the Plaud recording and its transcript. Full flow." | The agent pulled the call through the Plaud MCP and turned it into business rules (pai/filha, 65-day window, status trap) kept in project memory. |
| Four questions asked by the agent, answered by the author: existing workspace · AppKit (TS/React) · tool-using agent (deterministic retrieval + LLM) · train the ML model for real | Scope and architecture locked before building. |
| "You can do everything without my supervision, go for it! Just commit everything to this repo." | Autonomous, phased build: one commit per layer, execution evidence committed as text. |
| "Pick up where you left off. My workspace was deleted; the new profile is …" | The agent re-pointed every file and rebuilt all six layers on the new workspace from the repo. |
| "The app is too simple … we need a monitoring dashboard with an integrated agent I can ask about the NIPs. Be more creative, but don't overcomplicate." | App v2: Painel, Fila, Radar and the embedded Genie agent. |
| A screenshot of the app: "Invalid scope, required scopes: genie" | The agent found the missing OAuth scope and redeployed. |
| "Build a Google Slides deck with our ideal storytelling for the FE Bar, following the visual pattern of this deck." | The deck generated as code on the reference visual system, with the demo script as speaker notes. |
| "Give context on the problem before the results: not everyone in the room, nor the AI evaluator, has it." | Deck and demo script restructured context-first; saved as a standing rule in memory. |

**Prompts inside the product**

- **Matcher** ([`04_intelligence/agent/matcher.py`](04_intelligence/agent/matcher.py)): the business
  rules as a numbered list, an explicit "status is not a reliable signal" rule, and a strict JSON
  contract (chosen guide, confidence, justification, parecer draft). SQL bounds the candidates to one
  beneficiary's guides in the window, so the LLM never searches: it only ranks and writes.
- **Genie space** ([`06_genie/build_space.py`](06_genie/build_space.py)): glossary, rules for
  answering in business language, the fine premise, sample questions and certified SQL, all versioned.

## 3. Patterns: what made it more than autocomplete

1. **Ground the build in real discovery, keep the data out.** The business rules came from the
   customer call. The repo holds only those rules plus synthetic data, and the generator plants each
   rule as a hard case.
2. **Decide first, then delegate.** The agent asked four architecture questions up front. The
   answers became locked decisions in memory, so later work didn't drift.
3. **Eval-driven, against a ground-truth oracle.** The generator knows the right guide for every NIP,
   so [`evaluate.py`](04_intelligence/agent/evaluate.py) scores the matcher by hard-case segment.
   - The first full run scored **63.5%**. Its confidence buckets (89.8% right at ≥ 0.8, 0% below)
     showed the model knew when it didn't know.
   - The agent traced the gap to a **data bug, not a prompt bug**: some synthetic guides were dated
     after their NIP, so the 65-day window dropped them. With the generator fixed, the matcher
     scored **96.6%** ([evidence/04](evidence/04_matcher_eval.md)).
   - A later run saw only 30 of the 208 NIPs. That exposed the row filter starving the gold tables
     and led to the masking + tags design.
4. **Deterministic retrieval + LLM.** SQL narrows the candidates; the LLM applies the rules, scores
   its confidence and drafts. Every choice can be explained to the regulator, and no vector search
   is needed, because recall is never the hard part.
5. **Everything as code, so the agent can rebuild it.** All of these are versioned and regenerable:
   - the pipeline (Asset Bundle) and the governance SQL;
   - the Genie space, whose `serialized_space` format the agent worked out from API errors;
   - the Lakebase loader, which re-grants the app identity;
   - the app, and the deck itself ([`deck/gslides/`](deck/gslides/)).

   When the workspace was deleted mid-build, the agent rebuilt all six layers from the repo.
6. **The agent verifies its own work.**
   - `databricks apps validate`: types, lint, build and tests.
   - A headless-browser run through every screen, with zero console errors.
   - HTTP checks on every API route, plus write-back round-trips.
   - Chart palettes run through a colorblind-safety validator.
   - The deck checked by a layout validator, with slide thumbnails reviewed by the agent.
7. **Memory across context limits.** The session outgrew the context window. Project facts, the
   environment and the author's feedback lived in memory files, so work resumed without re-briefing.
8. **Humans keep the irreversible calls.** Three of them stayed with the author: making the repo
   public, granting data to all workspace users and sharing the deck. Automatic safety checks
   stopped the agent from taking the first two on its own.
   - Commits pass the secret-scanning hooks, which were never bypassed.
   - Screenshots entered the deck through a PPTX round-trip instead of public links.

## 4. Where the AI got it wrong, and what caught it

| Miss | Caught by | Lesson |
|---|---|---|
| Synthetic guides dated after their NIP | The eval (63.5%) | Evals test the data, not only the model. |
| Row filter starving the gold tables | The eval saw 30 of 208 NIPs | Governance changes need a row-count check. |
| Agent in the app missing the `genie` OAuth scope | The author, in the browser | The agent tested with the CLI's all-APIs token, broader than a real user's. Test with the user's identity. |
| Slides API refused private images | API error | A PPTX round-trip instead of making files public. |

## 5. An advanced-usage view

| Level | How AI is used | Here |
|---|---|---|
| 1. Autocomplete | Suggests the next line. | — |
| 2. Chat assistant | Answers questions; the human copies and runs. | — |
| 3. Agent with tools | Runs commands, reads errors, iterates on one task. | Every layer |
| 4. Autonomous, with evals and guardrails | Owns a goal end to end, measures itself against an oracle, keeps memory, leaves the irreversible calls to the human. | **This build** |
| 5. A team of agents in CI | Parallel agents per workstream; evals and review agents gate every merge; production feedback improves the prompts. | Next step |

**What level 5 looks like for this project** (not built yet):

- **Evals as a merge gate.** Run `evaluate.py` on every change to the prompt, the rules or the data,
  and block the merge if any hard-case segment drops (for example, out-of-window below 75%).
- **The analyst teaches the agent.** Every decision in `analyst_feedback` (approve, adjust, reject)
  becomes a labeled example. The agent tracks drift weekly and re-tunes the prompt and the
  confidence cut against it. With MLflow tracing, each parecer is judged for grounding in the ANS rol.
- **Parallel agents, one per layer** (pipeline, app, deck), each in its own git worktree, with a
  review agent (Isaac Review) checking every change before it merges.
- **The confidence gate as a business decision.** Above the cut, with a favorable rol check, the NIP
  closes with no human. The business moves the cut as the eval and the analysts' feedback earn trust.
