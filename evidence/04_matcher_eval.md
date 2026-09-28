# Evidence — NIP->VPP matcher accuracy

Model: `databricks-gpt-6-sol` (Databricks Foundation Model API). Deterministic 65-day + beneficiary retrieval, LLM rule-aware ranking.

**Overall accuracy: 96.6%** on 208 NIPs (exact manifestação-id match vs. ground truth).

## Accuracy by planted hard-case type
| Segment | N | Accuracy |
|---|---|---|
| Complaint -> PARENT guide (pai) | 147 | 96.6% |
| Complaint -> CHILD (filha) | 61 | 96.7% |
| Resolved NIPs (status trap) | 88 | 97.7% |
| Unresolved NIPs | 120 | 95.8% |
| Multi-VPP ambiguity | 32 | 93.8% |
| Has out-of-window distractor | 14 | 78.6% |
| Beneficiary cited the VPP number | 60 | 95.0% |

## Confidence calibration
| Confidence band | N | Accuracy |
|---|---|---|
| high (>= 0.8) | 208 | 96.6% |

> The confidence gate is what enables safe automation: high-confidence matches can auto-close; low-confidence ones stay with a human.

## Sample decisions (with drafted parecer)

**MAN-0000020** — correct · conf 0.99 · pred `MAN-0000018` vs exp `MAN-0000018` (PROCEDIMENTO)
- justificativa: O ultrassom do bebê mencionado na reclamação corresponde à ultrassonografia obstétrica da guia VPP0000010. Por se tratar de exame, a manifestação correta é a guia pai.
- parecer sugerido: A reclamação refere-se à ultrassonografia obstétrica solicitada na VPP0000010. A negativa deve ser reavaliada, com esclarecimento de seus fundamentos e comunicação do resultado ao beneficiário, incluindo as providências para realização do exame caso seja autorizado.

**MAN-0000028** — correct · conf 0.99 · pred `MAN-0000027` vs exp `MAN-0000027` (MEDICAMENTO)
- justificativa: A reclamação trata da negativa do medicamento da quimioterapia, item registrado na guia filha VPP0000015. A guia pai contém consulta e diária de internação, não o medicamento reclamado.
- parecer sugerido: A reclamação refere-se à negativa do medicamento de quimioterapia registrado na manifestação MAN-0000027, vinculada à VPP0000015. Solicita-se à operadora que reavalie a negativa e apresente sua fundamentação, informando ao beneficiário as providências adotadas para assegurar a co

**MAN-0000189** — MISS · conf 0.99 · pred `MAN-0000188` vs exp `MAN-0000187` (PROCEDIMENTO)
- justificativa: A reclamação trata da colocação de stent, correspondente ao stent farmacológico (OPME) registrado na guia filha. O status atual de aprovado não afasta a reclamação sobre a recusa e a espera relatadas.
- parecer sugerido: A VPP filha VPP0000105, referente ao stent farmacológico, consta atualmente aprovada. Solicita-se à operadora esclarecer a recusa relatada, confirmar se o material foi efetivamente liberado e informar as providências para viabilizar o atendimento sem demora, considerando a piora 
