-- ============================================================================
-- GOLD — analytics- and serving-ready (materialized views).
-- Feeds the agent (vpp_candidatas), the app/Lakebase (nip_queue), Genie
-- (beneficiario_360), and the ML model (callcenter_features).
-- ============================================================================

-- One row per VPP / VPP_FILHA manifestação, with its procedures aggregated.
-- This is the candidate pool the NIP->VPP agent retrieves from.
CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_gold.gold_vpp_candidatas
COMMENT 'VPP guides (parent + child) with aggregated procedures — candidate pool for the matcher.'
AS
WITH procs AS (
  SELECT
    manifestacao_id,
    collect_list(struct(codigo_tuss, descricao_procedimento, categoria, tipo_item, status_item, valor)) AS procedimentos,
    concat_ws(' | ', collect_list(descricao_procedimento)) AS procedimentos_texto,
    max(CASE WHEN tipo_item IN ('MATERIAL', 'MEDICAMENTO', 'OPME') THEN 1 ELSE 0 END) AS tem_material_med,
    count(*) AS n_itens
  FROM wks_brabo_demo_catalog.nip_vpp_silver.silver_procedimentos
  GROUP BY manifestacao_id
)
SELECT
  m.manifestacao_id,
  m.beneficiario_id,
  m.tipo,                              -- 'VPP' (parent) or 'VPP_FILHA' (child)
  m.manifestacao_pai_id,
  m.vpp_numero,
  m.data_criacao,
  m.status,
  m.descricao,
  coalesce(p.n_itens, 0)          AS n_itens,
  coalesce(p.tem_material_med, 0) AS tem_material_med,
  p.procedimentos,
  p.procedimentos_texto,
  -- text blob used for embedding / vector search
  concat_ws('. ',
    concat('Guia ', coalesce(m.vpp_numero, ''), ' (', m.tipo, ')'),
    m.descricao,
    concat('Procedimentos: ', coalesce(p.procedimentos_texto, ''))
  ) AS texto_para_busca
FROM wks_brabo_demo_catalog.nip_vpp_silver.silver_manifestacoes m
LEFT JOIN procs p USING (manifestacao_id)
WHERE m.tipo IN ('VPP', 'VPP_FILHA');

-- One row per NIP, enriched, with an SLA countdown. Drives the analyst queue / app.
CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_gold.gold_nip_queue
COMMENT 'Open + historical NIPs with SLA countdown against the 5-day ANS deadline.'
AS SELECT
  n.manifestacao_id            AS nip_id,
  n.beneficiario_id,
  b.nome                       AS beneficiario_nome,
  b.plano_id,
  pl.nome_plano,
  pl.segmentacao               AS plano_segmentacao,
  n.descricao                  AS reclamacao_texto,
  n.data_criacao,
  n.prazo_ans,
  n.vpp_numero                 AS vpp_citada,
  n.status,
  (n.data_resolucao IS NOT NULL) AS resolvida,
  n.parecer_texto,
  n.analista_id,
  n.data_resolucao,
  datediff(to_date(n.prazo_ans), current_date()) AS dias_para_prazo,
  CASE
    WHEN n.data_resolucao IS NOT NULL                         THEN 'RESOLVIDA'
    WHEN datediff(to_date(n.prazo_ans), current_date()) < 0   THEN 'VENCIDA'
    WHEN datediff(to_date(n.prazo_ans), current_date()) <= 1  THEN 'CRITICA'
    WHEN datediff(to_date(n.prazo_ans), current_date()) <= 3  THEN 'ATENCAO'
    ELSE 'NO_PRAZO'
  END AS sla_status
FROM wks_brabo_demo_catalog.nip_vpp_silver.silver_manifestacoes n
JOIN wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario b USING (beneficiario_id)
LEFT JOIN wks_brabo_demo_catalog.nip_vpp_silver.silver_plano pl USING (plano_id)
WHERE n.tipo = 'NIP';

-- Beneficiary 360 for Genie / analyst context.
CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_gold.gold_beneficiario_360
COMMENT 'One row per beneficiary: plan, activity counts, sentiment — for Genie NL queries.'
AS
WITH man AS (
  SELECT beneficiario_id,
    sum(CASE WHEN tipo = 'VPP' THEN 1 ELSE 0 END)       AS n_vpp,
    sum(CASE WHEN tipo = 'VPP_FILHA' THEN 1 ELSE 0 END) AS n_vpp_filha,
    sum(CASE WHEN tipo = 'NIP' THEN 1 ELSE 0 END)       AS n_nip
  FROM wks_brabo_demo_catalog.nip_vpp_silver.silver_manifestacoes
  GROUP BY beneficiario_id
),
cc AS (
  SELECT beneficiario_id, count(*) AS n_interacoes, avg(sentimento_score) AS avg_sentimento
  FROM wks_brabo_demo_catalog.nip_vpp_silver.silver_callcenter
  GROUP BY beneficiario_id
)
SELECT
  b.beneficiario_id, b.nome, b.uf, b.plano_id, pl.nome_plano, pl.segmentacao AS plano_segmentacao,
  coalesce(man.n_vpp, 0)        AS n_vpp,
  coalesce(man.n_vpp_filha, 0)  AS n_vpp_filha,
  coalesce(man.n_nip, 0)        AS n_nip,
  coalesce(cc.n_interacoes, 0)  AS n_interacoes_callcenter,
  round(coalesce(cc.avg_sentimento, 0), 3) AS avg_sentimento
FROM wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario b
LEFT JOIN wks_brabo_demo_catalog.nip_vpp_silver.silver_plano pl USING (plano_id)
LEFT JOIN man USING (beneficiario_id)
LEFT JOIN cc  USING (beneficiario_id);

-- Per-beneficiary features + label for the NIP-propensity ML model.
CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_gold.gold_callcenter_features
COMMENT 'ML training table: call-center features per beneficiary + abriu_nip label.'
AS
WITH agg AS (
  SELECT
    beneficiario_id,
    count(*)                                                     AS n_interacoes,
    round(avg(sentimento_score), 4)                             AS avg_sentimento,
    round(min(sentimento_score), 4)                             AS min_sentimento,
    sum(CASE WHEN sentimento_score < -0.2 THEN 1 ELSE 0 END)     AS n_interacoes_negativas,
    sum(protocolos_abertos)                                      AS total_protocolos,
    round(avg(duracao_seg), 1)                                  AS avg_duracao_seg,
    max(data_interacao)                                          AS ultima_interacao
  FROM wks_brabo_demo_catalog.nip_vpp_silver.silver_callcenter
  GROUP BY beneficiario_id
),
nip_ben AS (
  SELECT DISTINCT beneficiario_id, 1 AS abriu_nip
  FROM wks_brabo_demo_catalog.nip_vpp_silver.silver_manifestacoes
  WHERE tipo = 'NIP'
)
SELECT
  b.beneficiario_id,
  b.plano_id,
  coalesce(a.n_interacoes, 0)             AS n_interacoes,
  coalesce(a.avg_sentimento, 0)           AS avg_sentimento,
  coalesce(a.min_sentimento, 0)           AS min_sentimento,
  coalesce(a.n_interacoes_negativas, 0)   AS n_interacoes_negativas,
  coalesce(a.total_protocolos, 0)         AS total_protocolos,
  coalesce(a.avg_duracao_seg, 0)          AS avg_duracao_seg,
  coalesce(datediff(current_date(), to_date(a.ultima_interacao)), 999) AS dias_desde_ultima,
  coalesce(n.abriu_nip, 0)                AS abriu_nip
FROM wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario b
LEFT JOIN agg     a USING (beneficiario_id)
LEFT JOIN nip_ben n USING (beneficiario_id);

-- Evaluation oracle (typed) for measuring matcher accuracy.
CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_gold.gold_eval_ground_truth
COMMENT 'Ground-truth: correct VPP manifestação per NIP + planted-case flags (evaluation only).'
AS SELECT
  nip_id,
  beneficiario_id,
  correct_manifestacao_id,
  correct_tipo,
  vpp_numero,
  episodio,
  complaint_type,
  CAST(nip_resolvida AS INT)              AS nip_resolvida,
  CAST(ambigua AS INT)                    AS ambigua,
  CAST(tem_distrator_fora_janela AS INT)  AS tem_distrator_fora_janela,
  CAST(cita_vpp AS INT)                   AS cita_vpp
FROM wks_brabo_demo_catalog.nip_vpp_bronze.bronze_ground_truth;
