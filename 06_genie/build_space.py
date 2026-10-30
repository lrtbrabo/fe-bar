"""
Build and push the Genie Space definition (tables + domain instructions + sample
questions + certified example SQL). The same space is embedded in the analyst app
as the "Agente NIP" and is reachable from Databricks One.

Writes the serialized space to 06_genie/space.json (versioned) and applies it with
`databricks genie update-space`.

Usage:  python build_space.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PROFILE = "wks-demo-brabo"
HERE = Path(__file__).parent
SPACE_ID = (HERE / ".space_id").read_text().strip()
G = "wks_demo_brabo_catalog.nip_vpp_gold"


def hid(text: str) -> str:
    """Stable 32-hex id derived from the content (Genie requires hex ids)."""
    return hashlib.md5(text.encode()).hexdigest()


INSTRUCTIONS = """# Agente NIP — instruções

Você apoia a coordenação de NIPs de uma operadora de saúde suplementar. Responda sempre em português do Brasil, de forma curta e direta, citando números.

## Como responder
- Fale a língua do negócio: não cite nomes de colunas nem valores técnicos (true/false, códigos como CRITICA ou VENCIDA). Diga "vence em até 1 dia", "vencida", "em aberto", "resolvida".
- Datas em dd/mm/aaaa, sem horário. Valores em reais no formato R$ 570 mil.
- Termine com uma recomendação prática quando fizer sentido (ex.: "priorize as 6 que vencem hoje").
- Ao explicar o risco do radar, agrupe os motivos em 2 ou 3 padrões com contagem (ex.: "5 com protocolos abertos, 4 com sentimento negativo"), em vez de listar beneficiário por beneficiário.

## Glossário
- NIP (Notificação de Intermediação Preliminar): reclamação do beneficiário registrada na ANS. A operadora tem 5 dias para responder; fora do prazo há risco de multa.
- VPP (Validação de Procedimento Prévio): guia de autorização prévia com os procedimentos solicitados. Cada NIP é associada a uma VPP pelo agente (coluna matched_manifestacao_id).
- Guia pai (tipo VPP) x item filho (tipo VPP_FILHA): reclamação sobre procedimento usa a guia pai; reclamação sobre material, medicamento ou OPME usa o item filho.
- tema: o tratamento ou cirurgia da guia associada (ex.: "colocação de stent no coração").

## Tabelas
- gold_nip_serving: uma linha por NIP. Use para fila, prazo, tema, confiança, parecer sugerido e justificativa.
  - sla_status: VENCIDA (passou do prazo), CRITICA (vence em até 1 dia), ATENCAO (até 3 dias), NO_PRAZO, RESOLVIDA.
  - "NIP aberta" ou "em aberto" = resolvida = false.
  - auto_resolvavel = true quando a confiança do agente é >= 0,8.
- gold_nip_rol_check: itens da guia associada a cada NIP comparados com o rol da ANS (no_rol) e com a segmentação do plano (segmentacao_cobre).
- gold_propensity_scores: chance de cada beneficiário abrir uma NIP (score de 0 a 1, faixa_risco ALTO >= 0,7, MEDIO >= 0,4). "Radar" ou "em risco" = abriu_nip = 0 e faixa_risco em ('ALTO','MEDIO'). A coluna motivos explica o risco.
- gold_beneficiario_360 e gold_vpp_candidatas: contexto do beneficiário e das guias.

## Regras
- Exposição a multa: use a premissa ilustrativa de R$ 30.000 por NIP vencida e aberta, e diga que é uma premissa.
- Tempo economizado: premissa de 17 minutos por NIP resolvida com o copiloto (25 min manual contra 8 min).
- Os nomes de beneficiários são mascarados pelo Unity Catalog; não tente revelá-los.
- Ao falar de uma NIP específica, traga reclamação resumida, tema, guia associada, confiança, justificativa e prazo.
"""

SAMPLE_QUESTIONS = [
    "Quais NIPs vencem em até 1 dia e qual o tema de cada uma?",
    "Qual a exposição a multa das NIPs vencidas, por tema?",
    "Quais temas concentram mais NIPs em aberto?",
    "Quantos beneficiários estão em risco alto de abrir NIP e por quê?",
    "Quantas NIPs abertas têm itens fora da segmentação do plano?",
]

EXAMPLES = [
    ("Exposição a multa das NIPs vencidas por tema",
     f"""SELECT coalesce(nullif(tema, ''), 'sem guia associada') AS tema,
       count(*) AS nips_vencidas,
       count(*) * 30000 AS exposicao_estimada_reais
FROM {G}.gold_nip_serving
WHERE sla_status = 'VENCIDA' AND NOT resolvida
GROUP BY 1
ORDER BY nips_vencidas DESC"""),
    ("Beneficiários em risco alto de abrir NIP",
     f"""SELECT beneficiario_id, nome, nome_plano, round(score, 2) AS score, motivos
FROM {G}.gold_propensity_scores
WHERE abriu_nip = 0 AND faixa_risco = 'ALTO'
ORDER BY score DESC"""),
    ("NIPs abertas com item fora da segmentação do plano",
     f"""SELECT DISTINCT s.nip_id, s.tema, s.nome_plano, s.plano_segmentacao, r.descricao_procedimento
FROM {G}.gold_nip_serving s
JOIN {G}.gold_nip_rol_check r ON r.nip_id = s.nip_id
WHERE NOT s.resolvida AND NOT r.segmentacao_cobre
ORDER BY s.nip_id"""),
]

TABLES = ["gold_beneficiario_360", "gold_nip_rol_check", "gold_nip_serving",
          "gold_propensity_scores", "gold_vpp_candidatas"]


def main():
    space = {
        "version": 2,
        "config": {"sample_questions": sorted(
            [{"id": hid(q), "question": [q]} for q in SAMPLE_QUESTIONS], key=lambda x: x["id"])},
        "data_sources": {"tables": [{"identifier": f"{G}.{t}"} for t in sorted(TABLES)]},
        "instructions": {
            "text_instructions": [{"id": hid(INSTRUCTIONS),
                                   "content": [l + "\n" for l in INSTRUCTIONS.splitlines()]}],
            "example_question_sqls": sorted(
                [{"id": hid(q), "question": [q], "sql": [l + "\n" for l in s.splitlines()]}
                 for q, s in EXAMPLES], key=lambda x: x["id"]),
        },
    }
    (HERE / "space.json").write_text(json.dumps(space, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    compact = json.dumps(space, ensure_ascii=False, separators=(",", ":"))
    out = subprocess.run(
        ["databricks", "genie", "update-space", SPACE_ID, "--serialized-space", compact,
         "--title", "Agente NIP · NIP VPP Copilot",
         "--description", "Fila de NIPs, guias VPP, checagem no rol ANS e radar de propensão (dados sintéticos).",
         "-p", PROFILE, "-o", "json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(out.stderr or out.stdout)
    print("updated space", SPACE_ID)


if __name__ == "__main__":
    main()
