# Evidence — Genie Space (natural-language analytics)

Space `NIP VPP Copilot` (id `01f1bb5ef4bf1eed83d9e601c7c66319`) over the gold tables. Analysts ask in plain Portuguese via Genie / Databricks One; Genie writes and runs the SQL.

## Q: Quantas NIPs existem por status de SLA?
_Há **5 status de SLA** com NIPs registradas. Exemplos incluem:
- **VENCIDA**: **106** NIPs
- **RESOLVIDA**: **88** NIPs
- **CRITICA**: **6** NIPs
- **ATENCAO**: **6** NIPs
- **NO_PRAZO**: **2** NIPs

Entre os status exibidos, **VENCIDA** é o mais frequente e **NO_PRAZO** o menos frequente._

Generated SQL:
```sql
SELECT `sla_status`, COUNT(*) AS `n_nips`
FROM `wks_demo_brabo_catalog`.`nip_vpp_gold`.`gold_nip_queue`
WHERE `sla_status` IS NOT NULL
GROUP BY `sla_status`
ORDER BY `n_nips` DESC
```
Result:
```
sla_status | n_nips
VENCIDA | 106
RESOLVIDA | 88
CRITICA | 6
ATENCAO | 6
NO_PRAZO | 2
```

## Q: Qual a taxa de matches auto resolvíveis (auto_resolvavel) entre as NIPs?
_A taxa de matches **auto resolvíveis** entre as NIPs é de **100%**. Nos dados consultados, há **208 NIPs com match** e **208 NIPs auto resolvíveis**, o que indica que **todas as NIPs com match** foram classificadas como auto resolvíveis._

_Você gostaria que a taxa de matches auto resolvíveis fosse calculada considerando todos os NIPs, incluindo os que não possuem nenhum match, em vez de apenas os que têm match?_

Generated SQL:
```sql
SELECT
  COUNT(DISTINCT CASE WHEN `auto_resolvavel` = true THEN `nip_id` END) AS `nips_auto_resolvaveis`,
  COUNT(DISTINCT `nip_id`) AS `total_nips_com_match`,
  try_divide(100.0 * COUNT(DISTINCT CASE WHEN `auto_resolvavel` = true THEN `nip_id` END),COUNT(DISTINCT `nip_id`)) AS `taxa_auto_resolvavel`
FROM `wks_demo_brabo_catalog`.`nip_vpp_gold`.`gold_nip_vpp_matches`
WHERE `nip_id` IS NOT NULL;
```
Result:
```
nips_auto_resolvaveis | total_nips_com_match | taxa_auto_resolvavel
208 | 208 | 100.00000000000000
```

## Q: Quais são os 5 beneficiários com mais interações no call center e menor sentimento médio?
_Os **5 beneficiários** com mais interações no call center e menor sentimento médio, entre os registros retornados, são:
- **Cecilia S.** (PE, **Hospitalar Nacional Copart**) — **5 interações** e sentimento médio **-0,639**
- **Maysa P.** (AP, **Saúde Total Nacional**) — **5 interações** e sentimento médio **-0,547**
- **Bernardo P.** (BA, **Ambulatorial Nacional**) — **5 interações** e sentimento médio **-0,540**
- **João G.** (SE, **Hospitalar Nacional Copart**) — **5 interações** e sentimento médio **-0,537**
- **Sra. N.** (MA, **Saúde Total Nacional**) — **5 interações** e sentimento médio **-0,524**

Nos 5 casos, o volume de interações foi igual, então a diferença veio do sentimento médio, com **Cecilia S.** apresentando o resultado mais negativo do grupo._

Generated SQL:
```sql
WITH ranked AS (
  SELECT
    `beneficiario_id`,
    `nome`,
    `uf`,
    `nome_plano`,
    `n_interacoes_callcenter`,
    `avg_sentimento`,
    RANK() OVER (
      ORDER BY `n_interacoes_callcenter` DESC, `avg_sentimento` ASC
    ) AS `rnk`
  FROM `wks_demo_brabo_catalog`.`nip_vpp_gold`.`gold_beneficiario_360`
  WHERE `n_interacoes_callcenter` IS NOT NULL
    AND `avg_sentimento` IS NOT NULL
)
SELECT
  `beneficiario_id`,
  `nome`,
  `uf`,
  `nome_plano`,
  `n_interacoes_callcenter`,
  `avg_sentimento`
FROM ranked
WHERE `rnk` <= 5
ORDER BY `rnk`, `n_interacoes_callcenter` DESC, `avg_sentimento` ASC;
```
Result:
```
beneficiario_id | nome | uf | nome_plano | n_interacoes_callcenter | avg_sentimento
BEN-000681 | Cecilia S. | PE | Hospitalar Nacional Copart | 5 | -0.639
BEN-000514 | Maysa P. | AP | Saúde Total Nacional | 5 | -0.547
BEN-000473 | Bernardo P. | BA | Ambulatorial Nacional | 5 | -0.54
BEN-001008 | João G. | SE | Hospitalar Nacional Copart | 5 | -0.537
BEN-000413 | Sra. N. | MA | Saúde Total Nacional | 5 | -0.524
```

