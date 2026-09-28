"""
NIP -> VPP matcher + parecer drafter.

Deterministic retrieval (beneficiary + 65-day window) narrows the candidate set;
the LLM then applies the business rules to pick the correct manifestação, score
its confidence, justify it, and draft the parecer (regulator response).

The candidate set is always bounded by ONE beneficiary's records (a handful of
guides), so there is no need for approximate/vector retrieval here — a design
choice, not a shortcut: the hard part is the rule-aware ranking, not recall.
"""
from __future__ import annotations

from datetime import timedelta

from dbx_common import CATALOG, chat_json, query

WINDOW_DAYS = 65

SYSTEM = """Você é um analista de saúde suplementar especialista em NIPs (Notificações de \
Intermediação Preliminar) da ANS. Sua tarefa é, dada a reclamação de uma NIP, encontrar entre as \
guias de autorização prévia (VPP) do beneficiário a manifestação correta que fundamenta a resposta.

Regras de negócio (aplique com rigor):
1. Escolha a guia cujos procedimentos se relacionam com o que a reclamação descreve. O beneficiário \
usa termos leigos; associe-os aos procedimentos técnicos das guias.
2. pai vs filha: se a reclamação é sobre MATERIAL, MEDICAMENTO ou OPME (ex.: prótese, stent, \
material cirúrgico, remédio), escolha a manifestação FILHA (tipo VPP_FILHA) que carrega esse item. \
Caso contrário (procedimento/exame/cirurgia/consulta), escolha a guia PAI (tipo VPP).
3. Status NÃO é sinal confiável: uma NIP pode já ter sido resolvida e o status do item alterado \
(negado -> aprovado). Nunca descarte uma guia só porque o status está 'APROVADO'.
4. Se a reclamação cita explicitamente um número de VPP, prefira a guia com esse número.
5. Em caso de empate, prefira a guia mais recente.

Responda SOMENTE com um objeto JSON:
{"chosen_manifestacao_id": "<id ou NENHUMA>", "tipo": "<VPP|VPP_FILHA|NENHUMA>", \
"confidence": <0.0-1.0>, "justificativa": "<1-2 frases>", "parecer_sugerido": "<rascunho do parecer da NIP>"}"""


def _fmt_candidate(c: dict) -> str:
    flag = " [contém MATERIAL/MEDICAMENTO/OPME]" if c.get("tem_material_med") else ""
    return (f"- id={c['manifestacao_id']} | tipo={c['tipo']} | vpp={c['vpp_numero']} | "
            f"criada={str(c['data_criacao'])[:10]} | status={c['status']}{flag}\n"
            f"    procedimentos: {c.get('procedimentos_texto') or c.get('descricao')}")


def build_user_prompt(nip: dict, candidates: list[dict]) -> str:
    cita = f"\nO beneficiário citou a guia: {nip['vpp_citada']}" if nip.get("vpp_citada") else ""
    cand_txt = "\n".join(_fmt_candidate(c) for c in candidates) or "(nenhuma guia no período)"
    return (f"RECLAMAÇÃO DA NIP (id={nip['nip_id']}, criada em {str(nip['data_criacao'])[:10]}):\n"
            f"\"{nip['reclamacao_texto']}\"{cita}\n\n"
            f"GUIAS CANDIDATAS DO BENEFICIÁRIO (janela de {WINDOW_DAYS} dias):\n{cand_txt}\n\n"
            f"Escolha a manifestação correta e redija o parecer.")


def match_nip(nip: dict, candidates: list[dict], model: str | None = None) -> dict:
    """Return the matcher decision for one NIP given its candidate guides."""
    if not candidates:
        return {"chosen_manifestacao_id": "NENHUMA", "tipo": "NENHUMA", "confidence": 0.0,
                "justificativa": "Nenhuma guia do beneficiário dentro da janela de 65 dias.",
                "parecer_sugerido": ""}
    kwargs = {"model": model} if model else {}
    out = chat_json(SYSTEM, build_user_prompt(nip, candidates), **kwargs)
    # normalize
    out.setdefault("chosen_manifestacao_id", "NENHUMA")
    out["confidence"] = float(out.get("confidence", 0.0) or 0.0)
    return out


def candidates_for(beneficiario_id: str, nip_data_criacao) -> list[dict]:
    """Deterministic retrieval: the beneficiary's VPP/VPP_FILHA guides within the 65-day window."""
    lo = (nip_data_criacao - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    hi = nip_data_criacao.strftime("%Y-%m-%d %H:%M:%S")
    return query(f"""
        SELECT manifestacao_id, tipo, manifestacao_pai_id, vpp_numero, data_criacao, status,
               descricao, n_itens, tem_material_med, procedimentos_texto
        FROM {CATALOG}.nip_vpp_gold.gold_vpp_candidatas
        WHERE beneficiario_id = '{beneficiario_id}'
          AND data_criacao BETWEEN TIMESTAMP '{lo}' AND TIMESTAMP '{hi}'
        ORDER BY data_criacao DESC
    """)
