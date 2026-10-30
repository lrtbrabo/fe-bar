"""
Build the FE Bar storytelling deck in Google Slides.

Starts from a copy of a Databricks field deck (for its master, footer, cover and closing),
deletes the copied content slides, and draws every slide with the same visual system:
navy #0B2026 / red #FF3621, DM Sans, red uppercase kicker, two-tone title, thin beige
cards, beige step boxes and a navy message banner. Each slide carries speaker notes with
the demo storytelling (see deck/roleplay-notes.md).

Usage:  python build_deck.py <presentation_id>      (the copy must already exist)
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

AUTH = Path.home() / ".vibe/marketplace/plugins/fe-google-tools/skills/google-auth/resources/google_auth.py"
QUOTA = "gcp-dev-field-eng-aiapiquota"
LAYOUT_BLANK = "g3f5209d8ff1_287_13371"  # "Content E - Blank" (master carries the footer)
E = 914400

NAVY, RED, RED_SOFT = "#0B2026", "#FF3621", "#FF5F46"
INK, BODY, MUTED, LABEL = "#0B2026", "#3D4F55", "#5A6B70", "#618794"
LINE, BEIGE, GREEN, ON_DARK, WHITE = "#DED7CC", "#F9F6F4", "#00A972", "#C4D0D3", "#FFFFFF"
FONT = "DM Sans"


def token() -> str:
    return subprocess.check_output([sys.executable, str(AUTH), "token"], text=True).strip()


def api(method: str, url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None)
    req.add_header("Authorization", f"Bearer {token()}")
    req.add_header("x-goog-user-project", QUOTA)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{e.code} {url}\n{e.read().decode()[:800]}")


def rgb(h: str) -> dict:
    h = h.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


class Slide:
    """Collects batchUpdate requests for one slide."""

    def __init__(self, sid: str):
        self.sid, self.reqs, self.n = f"nip_{sid}", [], 0  # Slides object IDs need 5+ chars

    def _id(self) -> str:
        self.n += 1
        return f"{self.sid}_{self.n:02d}"

    def _box(self, oid, kind, x, y, w, h):
        self.reqs.append({"createShape": {"objectId": oid, "shapeType": kind, "elementProperties": {
            "pageObjectId": self.sid,
            "size": {"width": {"magnitude": int(w * E), "unit": "EMU"}, "height": {"magnitude": int(h * E), "unit": "EMU"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": int(x * E), "translateY": int(y * E), "unit": "EMU"}}}})

    def rect(self, x, y, w, h, fill=WHITE, line=LINE, kind="RECTANGLE", text=None, valign="MIDDLE"):
        oid = self._id()
        self._box(oid, kind, x, y, w, h)
        props = {"shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(fill)}}}, "contentAlignment": valign}
        fields = "shapeBackgroundFill.solidFill.color,contentAlignment,outline"
        if line:
            props["outline"] = {"outlineFill": {"solidFill": {"color": {"rgbColor": rgb(line)}}},
                                "weight": {"magnitude": 1, "unit": "PT"}}
        else:
            props["outline"] = {"propertyState": "NOT_RENDERED"}
        self.reqs.append({"updateShapeProperties": {"objectId": oid, "shapeProperties": props, "fields": fields}})
        if text:
            self._text(oid, *text)
        return oid

    def text(self, x, y, w, h, paras, align="START", valign="TOP", space_below=0):
        """paras: list of paragraphs; each paragraph is a list of (text, size, color, bold) runs."""
        oid = self._id()
        self._box(oid, "TEXT_BOX", x, y, w, h)
        self.reqs.append({"updateShapeProperties": {"objectId": oid, "shapeProperties": {"contentAlignment": valign},
                                                    "fields": "contentAlignment"}})
        self._text(oid, paras, align, space_below)
        return oid

    def _text(self, oid, paras, align="START", space_below=0):
        full = "\n".join("".join(r[0] for r in p) for p in paras)
        self.reqs.append({"insertText": {"objectId": oid, "text": full, "insertionIndex": 0}})
        i = 0
        for p in paras:
            for t, size, color, bold in p:
                if t:
                    self.reqs.append({"updateTextStyle": {"objectId": oid, "textRange": {"type": "FIXED_RANGE", "startIndex": i, "endIndex": i + len(t)},
                                      "style": {"fontFamily": FONT, "fontSize": {"magnitude": size, "unit": "PT"}, "bold": bold,
                                                "foregroundColor": {"opaqueColor": {"rgbColor": rgb(color)}}},
                                      "fields": "fontFamily,fontSize,bold,foregroundColor"}})
                i += len(t)
            i += 1  # paragraph break
        self.reqs.append({"updateParagraphStyle": {"objectId": oid, "textRange": {"type": "ALL"},
                          "style": {"alignment": align, "lineSpacing": 100, "spaceBelow": {"magnitude": space_below, "unit": "PT"},
                                    "spaceAbove": {"magnitude": 0, "unit": "PT"}},
                          "fields": "alignment,lineSpacing,spaceBelow,spaceAbove"}})

    # ---- composite blocks (measured from the reference deck) -------------------------
    def header(self, kicker, title, red, subtitle):
        self.text(0.6, 0.38, 12.0, 0.3, [[(kicker.upper(), 10, RED, True)]])
        self.text(0.6, 0.66, 12.2, 0.6, [[(title, 24, INK, True), (red, 24, RED, True)]])
        self.text(0.6, 1.24, 12.2, 0.32, [[(subtitle, 11.5, MUTED, False)]])

    def banner(self, lead, rest, y=5.6, h=0.9, size=13):
        self.rect(0.6, y, 12.15, h, fill=NAVY, line=None, kind="ROUND_RECTANGLE",
                  text=([[(lead + " ", size, WHITE, True), (rest, size, ON_DARK, False)]], "CENTER"))

    def source(self, txt):
        self.text(0.6, 6.68, 12.2, 0.25, [[(txt, 7.5, LABEL, False)]])

    def card(self, x, y, w, h, label, heading, bullets, foot, hsize=16, bsize=11.5):
        self.rect(x, y, w, h)
        pad, iw = 0.3, w - 0.6
        self.text(x + pad, y + 0.15, iw, 0.3, [[(label.upper(), 9.5, LABEL, True)]])
        hh = 0.5 if hsize >= 16 else 0.62
        self.text(x + pad, y + 0.45, iw, hh, [[(heading, hsize, INK, True)]])
        by = y + 0.45 + hh + 0.15
        self.text(x + pad, by, iw, h - (by - y) - 0.75,
                  [[("•  ", bsize, RED, True), (b, bsize, BODY, False)] for b in bullets], space_below=7)
        self.text(x + pad, y + h - 0.65, iw, 0.45, [[(foot, 12 if hsize >= 16 else 11, RED, True)]], valign="BOTTOM")

    def info_card(self, x, y, w, h, label, heading, body):
        self.rect(x, y, w, h)
        self.text(x + 0.3, y + 0.15, w - 0.6, 0.3, [[(label.upper(), 9.5, LABEL, True)]])
        self.text(x + 0.3, y + 0.45, w - 0.6, 0.4, [[(heading, 13, INK, True)]])
        self.text(x + 0.3, y + 0.85, w - 0.6, h - 0.95, [[(body, 10, BODY, False)]])

    def metric(self, x, y, w, h, number, caption, heading, body):
        self.rect(x, y, w, h)
        self.text(x + 0.25, y + 0.15, w - 0.45, 0.65, [[(number, 26, GREEN, True)]])
        self.text(x + 0.25, y + 0.77, w - 0.45, 0.3, [[(caption, 9.5, BODY, False)]])
        self.text(x + 0.25, y + 1.15, w - 0.45, 0.35, [[(heading, 13, INK, True)]])
        self.text(x + 0.25, y + 1.5, w - 0.45, h - 1.55, [[(body, 10, BODY, False)]])

    def steps(self, y, dark_label, items, h=1.1, dark_w=2.3, stacked=False):
        self.rect(0.6, y, dark_w, h, fill=NAVY, line=None, kind="ROUND_RECTANGLE",
                  text=([[(l, 10, WHITE, True)] for l in dark_label.upper().split("\n")], "CENTER"))
        n = len(items)
        gap = 0.15
        x0 = 0.6 + dark_w + gap
        w = (12.75 - x0 - gap * (n - 1)) / n
        for i, (num, title, desc) in enumerate(items):
            paras = ([[(num, 14, RED, True)], [(title, 11, INK, True)], [(desc, 9, BODY, False)]] if stacked
                     else [[(f"{num}  ", 12, RED, True), (title, 12, INK, True)], [(desc, 9, BODY, False)]])
            self.rect(x0 + i * (w + gap), y, w, h, fill=BEIGE, line=LINE, kind="ROUND_RECTANGLE", text=(paras, "CENTER"))

    def boxes(self, y, items, h=1.5):
        n, gap = len(items), 0.15
        w = (12.15 - gap * (n - 1)) / n
        for i, (num, title, desc) in enumerate(items):
            self.rect(0.6 + i * (w + gap), y, w, h, fill=BEIGE, line=LINE, kind="ROUND_RECTANGLE",
                      text=([[(f"{num}  ", 12, RED, True), (title, 12, INK, True)], [(desc, 9.5, BODY, False)]], "CENTER"))

    def screenshot(self, name, callouts):
        # frame where the app screenshot goes (replaced by the picture in the PPTX pass)
        self.rect(0.6, 1.8, 7.45, 4.66, fill=BEIGE, line=LINE,
                  text=([[(f"[print: {name}]", 11, LABEL, True)]], "CENTER"))
        y, step = 1.8, 4.66 / len(callouts)
        for i, (head, body) in enumerate(callouts, 1):
            self.text(8.35, y, 0.4, 0.4, [[(str(i), 14, RED, True)]])
            self.text(8.75, y, 4.0, 0.4, [[(head, 13, INK, True)]])
            self.text(8.75, y + 0.4, 4.0, step - 0.5, [[(body, 10.5, BODY, False)]])
            y += step

    def divider(self, kicker, line1, red, subtitle):
        self.rect(0, 0, 13.333, 7.5, fill=NAVY, line=None)
        self.rect(0.6, 2.35, 0.08, 2.3, fill=RED, line=None)
        self.text(0.95, 2.25, 6.0, 0.4, [[(kicker, 12, RED_SOFT, True)]])
        self.text(0.95, 2.75, 11.5, 1.4, [[(line1, 34, WHITE, True)], [(red, 34, RED, True)]])
        self.text(0.95, 4.25, 10.5, 0.6, [[(subtitle, 14, ON_DARK, False)]])


# ------------------------------------------------------------------------------------------
# The storyline: outcome first, then problem, solution (one move per screen), proof, value,
# how it works, decisions, next step.
# ------------------------------------------------------------------------------------------
def build_slides():
    S = []

    s = Slide("s02"); S.append((s, """Abra com o resultado, antes de qualquer arquitetura. "Toda NIP que chega na ANS dá 5 dias para a operadora responder; passou disso, é multa. Este protótipo pega o backlog que hoje representa R$ 3,2 milhões de exposição e deixa cada NIP pronta para resolver." Aponte os três números e diga que o resto da conversa explica como se chega neles."""))
    s.header("O resultado, antes de tudo", "O backlog que custava R$ 3,2 mi ", "ficou pronto para resolver",
             "Protótipo ponta a ponta na Databricks para uma operadora de saúde, sobre um caso real e com dados sintéticos.")
    s.metric(0.6, 1.85, 3.95, 2.4, "R$ 3,2 mi", "de exposição a multa no backlog", "106 NIPs vencidas",
             "Premissa ilustrativa de R$ 30 mil por NIP fora do prazo, editável na tela pela própria operadora.")
    s.metric(4.7, 1.85, 3.95, 2.4, "25 → 8 min", "por NIP, da busca ao parecer", "120 de 120 prontas",
             "Toda NIP aberta já tem a guia inferida, com confiança de 80% ou mais, e o parecer rascunhado.")
    s.metric(8.8, 1.85, 3.95, 2.4, "77%", "das NIPs antecipadas pelo modelo", "Prevenção no call center",
             "O radar aponta quem vai abrir NIP antes da reclamação chegar à ANS (teste fora da amostra).")
    s.steps(4.45, "Um app,\nquatro movimentos", [("1", "Enxergar", "o risco no painel"), ("2", "Perguntar", "ao agente, em português"),
            ("3", "Resolver", "cada NIP em minutos"), ("4", "Prevenir", "a próxima reclamação")])
    s.banner("Em uma frase:", "o copiloto acha a guia certa, escreve o parecer e aponta quem vai reclamar antes de reclamar.", y=5.75, h=0.7, size=12)
    s.source("Números do protótipo sobre 208 NIPs sintéticas. Premissas de multa e de tempo economizado são ilustrativas.")

    s = Slide("s03"); S.append((s, """Transição: "Primeiro, o problema, do jeito que a área de NIPs descreve." Fale devagar aqui; é o momento de a executiva concordar com a dor."""))
    s.divider("01  ·  O PROBLEMA", "Cinco dias para responder,", "ou a multa chega",
              "Como a NIP nasce, quanto custa hoje e por que achar a guia certa é difícil.")

    s = Slide("s04"); S.append((s, """Conte a jornada da esquerda para a direita: a negativa, a ouvidoria que não resolve, a reclamação na ANS e a corrida do analista para achar a guia e escrever o parecer em 5 dias. "Hoje isso leva uns 25 minutos por NIP, e às vezes três analistas abrem a mesma." Feche com a frase da faixa escura: o sinal aparece antes, no call center. Ela prepara o radar."""))
    s.header("Como é hoje", "Cada NIP vira ", "uma corrida manual contra o prazo",
             "Quando a negativa não se resolve na ouvidoria, o beneficiário reclama na ANS. A partir daí são 5 dias.")
    s.metric(0.6, 1.85, 3.95, 2.4, "5 dias", "de prazo da ANS por NIP", "Depois disso, multa",
             "Cada NIP fora do prazo é exposição direta a multa do regulador.")
    s.metric(4.7, 1.85, 3.95, 2.4, "25 min", "de analista por NIP", "Busca e parecer à mão",
             "O analista varre as guias do beneficiário, cruza com a reclamação e escreve a resposta.")
    s.metric(8.8, 1.85, 3.95, 2.4, "106", "NIPs vencidas no backlog", "R$ 3,2 mi em risco",
             "Com a premissa de R$ 30 mil por NIP. E mais de um analista pode abrir a mesma NIP.")
    s.steps(4.45, "A jornada\nda NIP", [("1", "Negativa", "procedimento ou material"), ("2", "Ouvidoria", "o caso não se resolve"),
            ("3", "NIP na ANS", "reclamação formal"), ("4", "Caça à guia", "entre várias VPPs"), ("5", "Parecer", "em até 5 dias")])
    s.banner("O sinal aparece antes:", "muitos beneficiários avisam no call center semanas antes de abrir a NIP.", y=5.75, h=0.7, size=12)
    s.source("Processo descrito pela área de NIPs de uma operadora de saúde (discovery, set/2026). Números do protótipo, com dados sintéticos.")

    s = Slide("s05"); S.append((s, """Aqui você ganha o líder técnico. "Não é uma busca: são três regras da área." Explique cada card em uma frase: pai ou filha, a janela de 65 dias e o status que muda depois que a NIP é resolvida. Diga que o gerador de dados planta esses casos de propósito, para o agente ser testado de verdade."""))
    s.header("Por que é difícil", "Achar a guia certa ", "é regra de negócio, não busca",
             "Um beneficiário tem várias guias, a reclamação usa palavras leigas e o dado muda depois que a NIP é resolvida.")
    s.card(0.6, 1.85, 3.95, 3.55, "Regra 1", "Guia pai ou item filho",
           ["Reclamação de procedimento usa a guia completa", "Material, medicamento ou OPME usa o item filho"],
           "Errar troca o objeto do parecer", hsize=14, bsize=11)
    s.card(4.7, 1.85, 3.95, 3.55, "Regra 2", "Janela de 65 dias",
           ["Só contam guias até 65 dias antes da NIP", "Guias antigas do mesmo tema confundem"],
           "Guia velha, parecer sobre outro caso", hsize=14, bsize=11)
    s.card(8.8, 1.85, 3.95, 3.55, "Regra 3", "Status que muda",
           ["Depois de resolvida, negado vira aprovado", "O status deixa de ser um sinal confiável"],
           "Casos antigos enganam a busca", hsize=14, bsize=11)
    s.banner("Por isso não basta um SQL:", "o agente aplica as três regras e explica cada escolha na tela.")
    s.source("Regras levantadas com a área de negócio na POC do cliente; reproduzidas no protótipo com casos difíceis plantados de propósito.")

    s = Slide("s06"); S.append((s, """Transição: "Agora, como o time trabalha com o copiloto." A partir daqui, cada slide é uma tela do app. Se estiver com o app aberto, alterne para a demo."""))
    s.divider("02  ·  A SOLUÇÃO", "Um centro de comando", "para as NIPs",
              "Enxergar, perguntar, resolver e prevenir, num só app, sobre o mesmo dado governado.")

    s = Slide("s07"); S.append((s, """Apresente o mapa da demo: quatro telas, quatro perguntas da coordenação. "Vou passar por elas nesta ordem." O ponto para o técnico: tudo lê o mesmo dado governado, então painel, agente e fila nunca discordam."""))
    s.header("Quatro movimentos", "Do painel à prevenção, ", "num só app",
             "Cada tela responde a uma pergunta da coordenação de NIPs.")
    w = (12.15 - 3 * 0.15) / 4
    for i, (lab, head, bul, foot) in enumerate([
        ("Enxergar", "Painel", ["Backlog por prazo ANS", "Exposição a multa em R$", "O que fazer agora"], "Como estamos hoje?"),
        ("Perguntar", "Agente NIP", ["Perguntas em português", "Resposta com dado e SQL", "Em nome de quem pergunta"], "E se eu quiser saber mais?"),
        ("Resolver", "Fila de NIPs", ["Guia inferida e o porquê", "Checagem no rol da ANS", "Parecer pronto para aprovar"], "Como resolvo esta NIP?"),
        ("Prevenir", "Radar", ["Quem vai abrir NIP", "Motivo em linguagem simples", "Ação do call center"], "Dá para evitar a próxima?"),
    ]):
        s.card(0.6 + i * (w + 0.15), 1.85, w, 3.55, lab, head, bul, foot, hsize=14, bsize=10.5)
    s.banner("Um dado só:", "o painel, o agente e a fila leem as mesmas tabelas governadas, então nunca discordam.")

    s = Slide("s08"); S.append((s, """Tell: "Isso é o que a coordenadora vê quando chega de manhã." Show: 120 abertas, 6 vencendo em até 1 dia, R$ 3,2 mi de exposição. Momento ao vivo: pergunte à executiva qual é a multa média deles e troque a premissa; tudo recalcula. Tell: "Cada número sai do dado governado. Não é planilha." """))
    s.header("Enxergar", "A coordenação vê ", "o risco em reais, não em linhas",
             "Posição da fila, exposição a multa e as próximas ações, numa tela.")
    s.screenshot("Painel", [("120 NIPs em aberto", "6 vencem em até 1 dia e 106 já passaram do prazo da ANS."),
                            ("R$ 3,2 mi de exposição", "A premissa de multa é editável: a executiva coloca o número dela e tudo recalcula."),
                            ("O que fazer agora", "Cada alerta leva direto à fila filtrada, ao radar ou ao agente.")])
    s.source("Premissas ilustrativas: R$ 30 mil por NIP vencida e 17 minutos economizados por NIP.")

    s = Slide("s09"); S.append((s, """O coração da demo. Abra a fila crítica e a NIP MAN-0002164: "a guia da cirurgia saiu, só falta o material". Mostre a guia escolhida (item filho, 99%), as três descartadas e o motivo de cada uma, a checagem no rol ("negado, mas no rol e coberto: reverter") e o parecer pronto. Clique em Aprovar. Tell: "Eram 25 minutos de busca e redação. Agora é uma revisão. Essa NIP saiu do risco de multa." """))
    s.header("Resolver", "Cada NIP vira ", "uma revisão de um minuto",
             "NIP MAN-0002164: a beneficiária reclama da banda gástrica que falta para a cirurgia bariátrica.")
    s.screenshot("Fila", [("Guia certa, 99% de confiança", "O agente escolhe o item filho (o material), não a guia da cirurgia."),
                          ("As outras três guias, e por quê", "Regra pai/filha, procedimento diferente e uma guia fora da janela de 65 dias."),
                          ("Checagem no rol da ANS", "Item negado, mas no rol e coberto pelo plano: a sugestão é reverter."),
                          ("Parecer pronto", "O analista revisa e aprova; a decisão fica gravada no Lakebase.")])
    s.source("Dados sintéticos. A explicação de cada descarte vem da tabela de guias avaliadas, publicada junto com o resultado do agente.")

    s = Slide("s10"); S.append((s, """Tell: "E se a coordenadora tiver uma pergunta que não está no painel?" Show: "Qual a exposição a multa por tema?" O agente responde por tema (stent R$ 570 mil, hemodiálise R$ 480 mil), com gráfico, tabela e o SQL; abra o SQL para o técnico. Tell: "Ele responde com as permissões de quem pergunta: o nome chega mascarado." Pergunta reserva: quais NIPs vencem em até 1 dia."""))
    s.header("Perguntar", "Qualquer pergunta, ", "com o dado governado",
             "O Agente NIP é o Genie dentro do app, a um clique de qualquer tela.")
    s.screenshot("Agente", [("Em português, com números", "\"Qual a exposição a multa por tema?\" Stent lidera, com R$ 570 mil."),
                            ("Mostra o SQL", "O técnico confere a consulta; o negócio confia na resposta."),
                            ("Com as permissões de quem pergunta", "Roda em nome do usuário: o dado pessoal chega mascarado pelo Unity Catalog.")])
    s.source("Genie space com glossário da área, regras de resposta e SQL certificado. O mesmo agente fica disponível no Databricks One.")

    s = Slide("s11"); S.append((s, """A ponte vem da NIP que você acabou de resolver: na linha do tempo, em 02/08 a beneficiária ligou e disse "Vou reclamar na ANS se não resolverem", sete semanas antes. "Ela avisou." Mostre o radar: 9 em risco alto e 67 em observação, cada um com o motivo. Acione o primeiro. Tell: "A NIP mais barata é a que não acontece." """))
    s.header("Prevenir", "A NIP mais barata ", "é a que não acontece",
             "O radar aponta quem ainda não abriu NIP, mas se comporta no call center como quem abriu.")
    s.screenshot("Radar", [("\"Vou reclamar na ANS se não resolverem.\"", "A beneficiária da NIP MAN-0002164 avisou no call center em 02/08, sete semanas antes."),
                           ("9 em risco alto, 67 em observação", "Cada um com o motivo: protocolos abertos, contatos negativos e sentimento."),
                           ("77% das NIPs antecipadas", "40 de 52 no teste fora da amostra. O call center aciona e registra a ação.")])
    s.source("Modelo de propensão registrado no Unity Catalog e servido em endpoint; pontuação em lote para o radar.")

    s = Slide("s12"); S.append((s, """Transição: "Isso funciona? Medimos." Saia da demo e volte para os slides."""))
    s.divider("03  ·  RESULTADOS", "O que o protótipo", "já provou",
              "Números medidos contra um gabarito, com os casos difíceis plantados de propósito.")

    s = Slide("s13"); S.append((s, """Fale para a executiva primeiro (96,6% de acerto, 100% das abertas prontas) e depois desça para o técnico na linha de baixo: o acerto por tipo de caso difícil. Seja honesto sobre o ponto fraco: a guia antiga do mesmo tema (78,6%) é onde o piloto vai calibrar regras e o corte de confiança."""))
    s.header("Provas", "Medido contra gabarito, ", "inclusive nos casos difíceis",
             "208 NIPs sintéticas com as armadilhas reais do processo: pai/filha, janela de 65 dias e status que muda.")
    s.metric(0.6, 1.85, 3.95, 2.4, "96,6%", "de acerto na guia, em 208 NIPs", "Associação NIP → VPP",
             "Busca determinística por beneficiário e janela; o LLM aplica as regras e redige o parecer.")
    s.metric(4.7, 1.85, 3.95, 2.4, "0,926", "ROC-AUC do modelo de propensão", "Radar de prevenção",
             "Identifica 77% das NIPs no teste fora da amostra, com precisão de 78%.")
    s.metric(8.8, 1.85, 3.95, 2.4, "100%", "das NIPs abertas prontas", "Confiança de 80% ou mais",
             "Toda NIP aberta tem guia inferida e parecer rascunhado; o corte decide o que pede revisão.")
    s.steps(4.45, "Acerto por\ncaso difícil", [("96,6%", "Guia pai", "procedimento"), ("96,7%", "Item filho", "material ou OPME"),
            ("97,7%", "Status muda", "NIP já resolvida"), ("93,8%", "Várias guias", "2 ou mais VPPs"), ("78,6%", "Guia antiga", "fora da janela")],
            stacked=True)
    s.banner("O caso mais difícil é a guia antiga do mesmo tema:", "é onde o piloto vai calibrar as regras e o corte de confiança.", y=5.75, h=0.7, size=12)
    s.source("Avaliação do agente e métricas do modelo no repositório do projeto (evidence/04 e evidence/05). Dados sintéticos.")

    s = Slide("s14"); S.append((s, """Troque de altitude de propósito: o card da esquerda fala com quem paga (multa, vazão, automação controlada), o da direita com quem opera (regras, rastreabilidade, LGPD). Termine devolvendo a premissa para a executiva: "Quanto vale para vocês? O número é de vocês." """))
    s.header("Valor", "O que muda ", "para quem paga e para quem opera",
             "O mesmo app responde ao custo e ao risco da executiva e à qualidade e à operação da área.")
    s.card(0.6, 1.85, 6.0, 3.55, "Patrocinador executivo", "Menos multa, mais vazão",
           ["Backlog de R$ 3,2 mi pronto para resolver", "Cerca de 560 h de analista por mês com 2.000 NIPs", "Automação gradual, com o corte controlado pelo negócio"],
           "KPI: NIPs no prazo e multas evitadas")
    s.card(6.75, 1.85, 6.0, 3.55, "Dono do domínio", "Qualidade e rastreabilidade",
           ["As regras da área embutidas e explicadas na tela", "Parecer rastreável e decisão do analista gravada", "Dados pessoais mascarados, conforme a LGPD"],
           "KPI: tempo por NIP e retrabalho")
    s.banner("Quanto vale para vocês?", "A premissa de multa é de vocês: o painel recalcula na hora.")
    s.source("Impacto ilustrativo: 2.000 NIPs por mês × 17 minutos economizados por NIP. Premissas editáveis no painel.")

    s = Slide("s15"); S.append((s, """Transição para o técnico: "Como isso está construído." Mantenha a executiva na sala com uma frase: tudo numa plataforma só, sem costurar ferramentas."""))
    s.divider("04  ·  COMO FUNCIONA", "Do dado bruto ao parecer,", "numa plataforma só",
              "A arquitetura, as decisões e por que Databricks.")

    s = Slide("s16"); S.append((s, """Leia a linha de cima como uma jornada: o dado entra pelo Lakeflow, é governado no Unity Catalog, a IA infere a guia e pontua o risco, o Lakebase serve a operação, o Genie responde e o app junta tudo. Depois, os três porquês. Se perguntarem da POC em BigQuery: o bloqueio era entregar para a área de negócio; aqui o app e o Genie entregam."""))
    s.header("Arquitetura", "Seis camadas, ", "uma jornada integrada",
             "O dado entra pelo Lakeflow, é governado no Unity Catalog e chega ao analista sem sair da plataforma.")
    s.boxes(1.85, [("1", "Lakeflow", "ingestão com Auto Loader, bronze, silver e gold"), ("2", "Unity Catalog", "masking de CPF e nome, tags e linhagem"),
                   ("3", "IA e ML", "agente NIP → VPP e modelo de propensão"), ("4", "Lakebase", "fila, radar e decisões em Postgres"),
                   ("5", "Genie", "perguntas em português, em nome do usuário"), ("6", "App", "o centro de comando do analista")])
    s.info_card(0.6, 3.55, 3.95, 1.85, "Um lugar só", "Sem costurar ferramentas",
                "A POC atual parou na hora de liberar para a área de negócio. Aqui o app e o Genie entregam.")
    s.info_card(4.7, 3.55, 3.95, 1.85, "Dado de saúde", "Governança de ponta a ponta",
                "Masking, tags e linhagem do Unity Catalog valem no app, no Genie e no SQL.")
    s.info_card(8.8, 3.55, 3.95, 1.85, "Onde o analista trabalha", "De volta ao Salesforce",
                "O conector nativo e bidirecional leva o parecer ao Salesforce: próximo passo do roadmap.")
    s.banner("Tudo versionado e reproduzível:", "pipeline em Asset Bundle, modelo registrado no Unity Catalog e app publicado com service principal.", size=12)

    s = Slide("s17"); S.append((s, """Este slide é para o técnico e para a nota de "decisões e trade-offs". Uma frase por card: busca fixa mais LLM porque cada escolha precisa ser explicável; Lakebase porque a operação lê e grava em milissegundos; masking no lugar de filtro de linha porque o filtro esvaziava a fila. Feche com o OBO: o agente nunca vê mais do que o usuário."""))
    s.header("Decisões e trade-offs", "Decisões que ", "priorizam o auditável",
             "Em saúde regulada, cada escolha precisa ser explicada ao regulador e ao analista.")
    s.card(0.6, 1.85, 3.95, 3.55, "Decisão 1", "Busca fixa e LLM, não um agente solto",
           ["SQL determinístico acha as guias do beneficiário na janela", "O LLM ranqueia, aplica as regras e redige"],
           "Cada escolha é explicável", hsize=14, bsize=11)
    s.card(4.7, 1.85, 3.95, 3.55, "Decisão 2", "Lakebase para a operação",
           ["Fila e radar em Postgres, com leitura em milissegundos", "Decisões do analista gravadas de volta"],
           "O warehouse fica para a análise", hsize=14, bsize=11)
    s.card(8.8, 1.85, 3.95, 3.55, "Decisão 3", "Masking em vez de filtro de linha",
           ["O filtro regional esvaziava a fila de quem não é admin", "O masking protege o dado sem perder NIPs"],
           "LGPD sem travar a operação", hsize=14, bsize=11)
    s.banner("E o agente roda em nome de quem pergunta:", "o Genie nunca vê mais do que o usuário pode ver.")

    s = Slide("s18"); S.append((s, """Feche com o pedido concreto. "O protótipo já roda ponta a ponta. O caminho é discovery das tabelas reais com a engenharia e um piloto de quatro semanas com um grupo de analistas, medindo tempo por NIP e NIPs dentro do prazo." Os três cards de cima são o que vem depois do piloto. Termine perguntando quem do time entraria no piloto."""))
    s.header("Próximo passo", "Do protótipo ao piloto ", "em quatro semanas",
             "O caminho que funciona: dado real, um grupo de analistas e métricas desde o primeiro dia.")
    s.info_card(0.6, 1.85, 3.95, 2.4, "Depois do piloto", "Fechar sozinho acima do corte",
                "NIPs com alta confiança e checagem favorável no rol seguem sem intervenção humana.")
    s.info_card(4.7, 1.85, 3.95, 2.4, "Integração", "Parecer direto no Salesforce",
                "O conector nativo leva o parecer de volta para onde o analista já trabalha.")
    s.info_card(8.8, 1.85, 3.95, 2.4, "Expansão", "Reembolso e rede credenciada",
                "As mesmas peças, com leitura de documentos e imagens por IA para os pedidos de reembolso.")
    s.steps(4.45, "Piloto de\n4 semanas", [("1", "Discovery", "tabelas reais com a engenharia"), ("2", "Conectar", "manifestações e Salesforce"),
            ("3", "Piloto", "um grupo de analistas"), ("4", "Medir", "tempo por NIP e prazo"), ("5", "Decidir", "corte de confiança")])
    s.banner("Proposta:", "piloto de quatro semanas com um grupo de analistas, medindo tempo por NIP e NIPs dentro do prazo.", y=5.75, h=0.7, size=12)
    return S


def main():
    pres = sys.argv[1]
    base = f"https://slides.googleapis.com/v1/presentations/{pres}"
    p = api("GET", base)
    slides = [s["objectId"] for s in p["slides"]]
    cover, closing = slides[0], slides[-1]

    # 1) remove the copied content slides, keep the cover and the closing
    reqs = [{"deleteObject": {"objectId": sid}} for sid in slides[1:-1]]
    # 2) cover: outcome-led title, presenter line. The copied cover's current text is read from
    #    the API (not hard-coded), and replaceAllText keeps the template's two-tone styling.
    ph = {el["shape"]["placeholder"]["type"]: el for el in p["slides"][0]["pageElements"]
          if el.get("shape", {}).get("placeholder")}
    runs = lambda t: [te["textRun"]["content"] for te in ph[t]["shape"].get("text", {}).get("textElements", []) if "textRun" in te]
    title = [r.strip() for r in runs("CENTERED_TITLE") if r.strip()]
    subtitle = "".join(runs("SUBTITLE")).strip()
    for old, new in [(title[0], "NIPs da ANS"), (title[-1], "no prazo"),
                     (subtitle, "NIP → VPP Copilot · Lucas Brabo · FE Bar · out/2026")]:
        if old != new:
            reqs.append({"replaceAllText": {"containsText": {"text": old, "matchCase": True}, "replaceText": new, "pageObjectIds": [cover]}})
    api("POST", base + ":batchUpdate", {"requests": reqs})

    # 3) draw the storyline
    built = build_slides()
    for i, (s, _) in enumerate(built, start=1):
        api("POST", base + ":batchUpdate", {"requests": [
            {"createSlide": {"objectId": s.sid, "insertionIndex": i, "slideLayoutReference": {"layoutId": LAYOUT_BLANK}}}] + s.reqs})
        print("built", s.sid, len(s.reqs), "requests")

    # 4) speaker notes (the storytelling) on every slide
    p = api("GET", base)
    notes_id = {sl["objectId"]: sl["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"] for sl in p["slides"]}
    # the copied cover/closing may carry the source deck's notes: clear them first
    reqs = []
    for sl in p["slides"]:
        if sl["objectId"] in (cover, closing):
            for el in sl["slideProperties"]["notesPage"].get("pageElements", []):
                if el["objectId"] == notes_id[sl["objectId"]] and el.get("shape", {}).get("text"):
                    reqs.append({"deleteText": {"objectId": el["objectId"], "textRange": {"type": "ALL"}}})
    if reqs:
        api("POST", base + ":batchUpdate", {"requests": reqs})
    cover_note = ("Abertura em 30 segundos: \"Toda NIP que chega na ANS dá 5 dias para a operadora responder. Passou disso, é multa. "
                  "Vou mostrar como o time trabalha com o copiloto: o painel da coordenação, a resolução de uma NIP real da fila e, "
                  "por fim, como evitar a próxima.\"")
    notes = [(cover, cover_note)] + [(s.sid, n) for s, n in built] + [(closing, "Encerramento: agradeça e abra para perguntas. Tenha o app aberto para responder mostrando.")]
    reqs = []
    for sid, text in notes:
        reqs.append({"insertText": {"objectId": notes_id[sid], "text": text, "insertionIndex": 0}})
    api("POST", base + ":batchUpdate", {"requests": reqs})
    print(f"done: https://docs.google.com/presentation/d/{pres}/edit")


if __name__ == "__main__":
    main()
