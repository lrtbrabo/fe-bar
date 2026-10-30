# Roteiro da demo: "um dia na coordenação de NIPs"

Duas personas na sala: a **executiva de negócio** (quem paga, pensa em multa, custo e risco) e o
**líder técnico** (quem convive com a solução, pensa em arquitetura, dados, segurança e integração).
Tudo em **tell → show → tell**: diga o que vai mostrar, mostre, e feche com o que isso significa para o negócio.

A história tem um arco simples, uma tela por ato:

| Ato | Tela | Pergunta que responde | Tempo |
|---|---|---|---|
| 0 | (slide) | Qual é o problema? | 0:30 |
| 1 | **Painel** | Como estamos e quanto isso custa? | 1:30 |
| 2 | **Agente NIP** | E se eu quiser perguntar outra coisa? | 1:00 |
| 3 | **Fila de NIPs** | Como o analista resolve uma NIP agora? | 3:00 |
| 4 | **Radar de prevenção** | Dá para evitar a próxima? | 1:30 |
| 5 | **Painel** de novo | O que mudou? | 0:30 |

---

## Ato 0 — enquadramento (30 s, antes de abrir o app)

> "Toda NIP que chega na ANS dá 5 dias para a operadora responder. Passou disso, é multa. Hoje o
> analista gasta uns 25 minutos por NIP só caçando a guia certa entre as guias do beneficiário e
> escrevendo o parecer. Vou mostrar como o time trabalha com o copiloto: primeiro o painel da
> coordenação, depois a resolução de uma NIP real da fila e, por fim, como evitar a próxima."

## Ato 1 — Painel: "como estamos" (1:30)

- **Tell:** "Isso é o que a coordenadora vê quando chega de manhã."
- **Show:**
  - Faixa de números: **120 NIPs em aberto, 6 vencem em até 1 dia, R$ 3,2 mi de exposição a multa**
    (106 vencidas × R$ 30 mil de premissa), **100% prontas para resolver** e **34 h de analista** que o
    copiloto devolve só no backlog atual.
  - **Momento ao vivo com a executiva:** "Qual a multa média de vocês?" Troque o valor em
    *Premissas do cálculo*: a exposição recalcula na hora. (Ela passa a dona do número.)
  - *Backlog por prazo ANS* e *Temas com mais NIPs*: stent no coração, hemodiálise e parto lideram.
- **Tell:** "Cada número sai do mesmo dado governado que alimenta o agente e a fila. Não é planilha."

## Ato 2 — Agente NIP: "pergunte o que quiser" (1:00)

- **Tell:** "E se a coordenadora tiver uma pergunta que não está no painel?"
- **Show:** clique em **"Onde está o dinheiro em risco? → Perguntar"**. O agente (Genie) responde por tema
  (stent R$ 570 mil, hemodiálise R$ 480 mil, quimioterapia R$ 450 mil…), com gráfico, tabela e o **SQL**
  que rodou. Abra o SQL rapidamente para o técnico.
- **Tell:** "Responde com as permissões de quem pergunta: o nome do beneficiário chega mascarado pelo
  Unity Catalog. É o mesmo agente que o time acessa pelo Databricks One."
- Pergunta reserva, se quiserem testar ao vivo: *"Quais NIPs vencem em até 1 dia e qual o tema de cada uma?"*

## Ato 3 — Fila: "resolver em 1 minuto" (3:00) — o coração da demo

- **Tell:** "Vamos resolver uma das 6 que vencem hoje." Painel → **Abrir fila crítica** → **MAN-0002164**
  (cirurgia bariátrica, Hospitalar Estadual).
- **Show, de cima para baixo:**
  1. **Reclamação:** "a guia da cirurgia saiu, só falta o material, e o hospital não marca sem ele."
  2. **Guia associada pelo agente:** item filho da VPP0001234 (banda gástrica, OPME), **99% de confiança**.
  3. **Guias avaliadas (4), e por que as outras saíram:** é aqui que se ganha o técnico.
     - a guia pai da mesma VPP foi descartada pela **regra pai/filha** (a reclamação é sobre o material);
     - uma guia de parto/internação, por **procedimentos que não correspondem**;
     - uma guia de maio, **fora da janela de 65 dias**.
  4. **Checagem no rol da ANS e no plano:** a banda gástrica está **negada**, mas **consta no rol** e o
     plano **cobre a segmentação** → *"Sugestão: reverter a negativa."*
  5. **Parecer sugerido**, já escrito. Clique **Aprovar e enviar**: fica gravado no Lakebase.
- **Tell:** "Isso era 25 minutos de busca e redação. Agora é uma revisão. Essa NIP saiu do risco de multa."
- **Ponte para o ato 4:** aponte a **Linha do tempo**: em **02/08** a beneficiária ligou e disse
  *"Vou reclamar na ANS se não resolverem."* Sete semanas antes da NIP. "Ela avisou. Dava para ter evitado."

## Ato 4 — Radar: "evitar a próxima" (1:30)

- **Tell:** "Então vamos olhar quem está avisando agora."
- **Show:** **Radar de prevenção**: **9 beneficiários em risco alto e 67 em observação**, que ainda não
  abriram NIP, cada um com o motivo em português ("3 protocolos abertos; 2 contatos negativos").
  O modelo identificaria **77% das NIPs** (40 de 52 no teste fora da amostra).
  Escolha **Ligar para o beneficiário** no primeiro da lista e clique **Acionar**.
- **Tell:** "A NIP mais barata é a que não acontece. O call center passa a trabalhar uma lista priorizada
  em vez de esperar a reclamação chegar no regulador."

## Ato 5 — volta ao Painel (30 s)

- **Show:** *Atividade recente* mostra o parecer aprovado e o beneficiário acionado; *horas já realizadas*
  subiu.
- **Fecho:** "Resumindo: o backlog que custava R$ 3,2 mi de exposição está 100% pronto para resolver, cada
  NIP vira uma revisão de um minuto, e o radar começa a cortar a entrada. Próximo passo: piloto com um grupo
  de analistas por quatro semanas, medindo tempo por NIP e NIPs dentro do prazo."

---

## Perguntas difíceis: executiva de negócio

| Pergunta | Resposta |
|---|---|
| Quanto isso economiza? | Use o painel: 17 min por NIP × volume. Com ~2.000 NIPs/mês, ~560 horas de analista. A exposição a multa vem da premissa que **ela** acabou de ajustar. |
| E se o agente errar? | Ele não decide sozinho: mostra a guia, o porquê, a checagem no rol e o analista aprova. Acertou **96,6%** das 208 NIPs no teste, e a confiança separa o que pode ir direto do que pede revisão. |
| Em quanto tempo isso vira realidade? | O protótipo já roda ponta a ponta. O caminho é discovery das tabelas reais com a engenharia e um piloto de 4 semanas. Semanas, não trimestres. |
| E o call center, muda o quê? | Ganha uma lista diária priorizada (o radar) com o motivo de cada caso e registra a ação. |

## Perguntas difíceis: líder técnico

| Pergunta | Resposta |
|---|---|
| Como vocês tratam pai/filha, a janela e os casos resolvidos? | Busca determinística (beneficiário + 65 dias) e o LLM aplica as regras ao ranquear. A tela de *Guias avaliadas* mostra o motivo de cada descarte. Avaliado por tipo de caso difícil (evidence/04). |
| De onde vem o dado e quem governa? | Lakeflow (Auto Loader) → Unity Catalog bronze/silver/gold, com masking de CPF/nome/email e tags de classificação. Linhagem automática. |
| Por que Lakebase? | A fila precisa de leitura rápida e o app grava decisões (OLTP). O gold é copiado para Postgres no Lakebase; o app escreve parecer e ações de retenção de volta. |
| O agente vê dado que o usuário não pode ver? | Não: o Genie roda **em nome do usuário** (escopo `dashboards.genie`), então vale o masking do Unity Catalog. |
| Integra com Salesforce? | Os analistas vivem no Salesforce: o conector nativo e bidirecional do Databricks leva o parecer de volta para lá. É o próximo passo do roadmap. |
| Por que não ficar na POC em BigQuery? | O bloqueio era liberar a ferramenta para a área de negócio. Aqui o app e o Genie/Databricks One entregam isso sem expor a complexidade da plataforma. |

## Trocando de altitude

Quando o técnico aprofundar ("como vocês sabem que o status mudou depois da resolução?"), responda com o
detalhe e devolva para a executiva: "…e para o negócio isso quer dizer que o agente continua acertando
mesmo em casos antigos, então dá para confiar na automação."

---

## Checklist antes de apresentar

1. Abra o app ~10 min antes (o app e o Lakebase podem estar dormindo; o primeiro acesso acorda os dois).
   Se o app estiver parado: `databricks apps start nip-vpp-copilot -p wks-demo-brabo`.
2. Faça uma pergunta ao agente antes da sessão, para aquecer o warehouse.
3. Zere as decisões de ensaio para a atividade começar limpa:
   `databricks psql --project nip-vpp -p wks-demo-brabo -- -d databricks_postgres -f 05_lakebase/reset_demo.sql`
4. Deixe abertas duas abas: **Painel** e **Fila → Vence em até 1 dia**.
5. Se o Genie demorar, siga para a fila e volte ao agente depois; nunca espere em silêncio.
