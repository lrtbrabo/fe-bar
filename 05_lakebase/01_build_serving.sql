-- ============================================================================
-- SERVING TABLES (gold) — built after the matcher publishes gold_nip_vpp_matches.
-- These feed the analyst app (via Lakebase reverse-ETL) and the Genie agent.
-- Run statement by statement (05_lakebase/load_lakebase.py does this).
-- ============================================================================

-- 1) One row per NIP: queue + inferred VPP + drafted parecer + the clinical "tema"
--    (the episode label of the matched guide's parent, e.g. "cirurgia bariátrica").
CREATE OR REPLACE TABLE wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_serving
COMMENT 'One row per NIP: SLA queue + inferred VPP + confidence + drafted parecer + tema (serving for app/Genie).'
AS SELECT
  q.nip_id, q.beneficiario_id, q.beneficiario_nome, q.plano_id, q.nome_plano, q.plano_segmentacao,
  q.reclamacao_texto, q.data_criacao, q.prazo_ans, q.dias_para_prazo, q.sla_status,
  q.status, q.resolvida, q.vpp_citada,
  m.matched_manifestacao_id, m.matched_tipo, m.confidence, m.auto_resolvavel,
  m.justificativa, m.parecer_sugerido,
  c.vpp_numero AS matched_vpp_numero,
  regexp_extract(p.descricao, 'prévia \\(([^)]+)\\)', 1) AS tema,
  CASE WHEN m.matched_tipo = 'VPP_FILHA' THEN 'Material, medicamento ou OPME'
       ELSE 'Procedimento' END AS categoria_reclamacao
FROM wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_queue q
LEFT JOIN wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_vpp_matches m ON m.nip_id = q.nip_id
LEFT JOIN wks_demo_brabo_catalog.nip_vpp_gold.gold_vpp_candidatas c ON c.manifestacao_id = m.matched_manifestacao_id
LEFT JOIN wks_demo_brabo_catalog.nip_vpp_gold.gold_vpp_candidatas p
  ON p.manifestacao_id = coalesce(c.manifestacao_pai_id, c.manifestacao_id);

-- 2) Every guide the beneficiary had before the NIP, with why the agent did or didn't pick it.
--    This is the explainability view ("por que esta guia?").
CREATE OR REPLACE TABLE wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_candidatas_avaliadas
COMMENT 'Per NIP: all prior guides of the beneficiary, the chosen one, and the reason others were discarded.'
AS
WITH chosen AS (
  SELECT s.nip_id, s.matched_manifestacao_id, s.matched_vpp_numero
  FROM wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_serving s
)
SELECT
  q.nip_id,
  c.manifestacao_id, c.tipo, c.vpp_numero, c.data_criacao, c.status,
  coalesce(c.procedimentos_texto, c.descricao) AS procedimentos_texto,
  datediff(q.data_criacao, c.data_criacao) AS dias_antes_nip,
  datediff(q.data_criacao, c.data_criacao) <= 65 AS dentro_janela,
  c.manifestacao_id = ch.matched_manifestacao_id AS escolhida,
  CASE
    WHEN c.manifestacao_id = ch.matched_manifestacao_id THEN 'Escolhida pelo agente'
    WHEN datediff(q.data_criacao, c.data_criacao) > 65 THEN 'Fora da janela de 65 dias'
    WHEN c.vpp_numero = ch.matched_vpp_numero AND c.tipo = 'VPP'
      THEN 'Guia pai: a reclamação é sobre o item (regra pai/filha)'
    WHEN c.vpp_numero = ch.matched_vpp_numero AND c.tipo = 'VPP_FILHA'
      THEN 'Item filho: a reclamação é sobre o procedimento da guia'
    ELSE 'Procedimentos não correspondem à reclamação'
  END AS motivo
FROM wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_queue q
JOIN wks_demo_brabo_catalog.nip_vpp_gold.gold_vpp_candidatas c
  ON c.beneficiario_id = q.beneficiario_id AND c.data_criacao <= q.data_criacao
LEFT JOIN chosen ch ON ch.nip_id = q.nip_id;

-- 3) Regulatory check: each item of the matched guide against the ANS rol and the plan's segmentation.
CREATE OR REPLACE TABLE wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_rol_check
COMMENT 'Per NIP: items of the matched guide checked against the (synthetic) ANS rol and the plan segmentation.'
AS SELECT
  s.nip_id,
  pr.codigo_tuss, pr.descricao_procedimento, pr.tipo_item, pr.status_item,
  r.obrigatorio_rol AS no_rol,
  r.segmentacao_cobertura,
  s.plano_segmentacao,
  CASE
    WHEN s.plano_segmentacao IN ('AMBULATORIAL+HOSPITALAR', 'REFERENCIA') THEN true
    WHEN s.plano_segmentacao = 'HOSPITALAR'   THEN r.segmentacao_cobertura IN ('HOSPITALAR', 'AMBULATORIAL+HOSPITALAR')
    WHEN s.plano_segmentacao = 'AMBULATORIAL' THEN r.segmentacao_cobertura IN ('AMBULATORIAL', 'AMBULATORIAL+HOSPITALAR')
    ELSE false
  END AS segmentacao_cobre,
  r.dut_texto
FROM wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_serving s
JOIN wks_demo_brabo_catalog.nip_vpp_silver.silver_procedimentos pr ON pr.manifestacao_id = s.matched_manifestacao_id
LEFT JOIN wks_demo_brabo_catalog.nip_vpp_silver.silver_rol_ans r ON r.codigo_tuss = pr.codigo_tuss;
