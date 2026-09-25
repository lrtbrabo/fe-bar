-- ============================================================================
-- SILVER — cleaned, typed, deduplicated (materialized views).
-- Empty strings -> NULL, dates -> timestamps, money -> DECIMAL.
-- ============================================================================

CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_manifestacoes
COMMENT 'Typed manifestacoes (NIP / VPP / VPP_FILHA).'
AS SELECT
  manifestacao_id,
  beneficiario_id,
  tipo,
  nullif(manifestacao_pai_id, '')            AS manifestacao_pai_id,
  to_timestamp(data_criacao)                 AS data_criacao,
  to_timestamp(data_atualizacao)             AS data_atualizacao,
  status,
  canal,
  nullif(prestador_id, '')                   AS prestador_id,
  descricao,
  nullif(vpp_numero, '')                     AS vpp_numero,
  to_timestamp(nullif(prazo_ans, ''))        AS prazo_ans,
  nullif(parecer_texto, '')                  AS parecer_texto,
  nullif(analista_id, '')                    AS analista_id,
  to_timestamp(nullif(data_resolucao, ''))   AS data_resolucao
FROM wks_brabo_demo_catalog.nip_vpp_bronze.bronze_manifestacoes
QUALIFY row_number() OVER (PARTITION BY manifestacao_id ORDER BY data_atualizacao DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_procedimentos
COMMENT 'Typed procedure line items.'
AS SELECT
  procedimento_id,
  manifestacao_id,
  codigo_tuss,
  descricao_procedimento,
  categoria,
  tipo_item,
  status_item,
  CAST(valor AS DECIMAL(12,2)) AS valor
FROM wks_brabo_demo_catalog.nip_vpp_bronze.bronze_procedimentos
QUALIFY row_number() OVER (PARTITION BY procedimento_id ORDER BY _ingested_at DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario
COMMENT 'Typed beneficiary dimension.'
AS SELECT
  beneficiario_id,
  nome,
  cpf,
  CAST(data_nascimento AS DATE) AS data_nascimento,
  plano_id,
  CAST(data_adesao AS DATE)     AS data_adesao,
  uf,
  email
FROM wks_brabo_demo_catalog.nip_vpp_bronze.bronze_dim_beneficiario
QUALIFY row_number() OVER (PARTITION BY beneficiario_id ORDER BY _ingested_at DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_plano
COMMENT 'Typed plan dimension.'
AS SELECT
  plano_id,
  nome_plano,
  segmentacao,
  abrangencia,
  CAST(lower(coparticipacao) = 'true' AS BOOLEAN) AS coparticipacao
FROM wks_brabo_demo_catalog.nip_vpp_bronze.bronze_dim_plano;

CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_rol_ans
COMMENT 'Typed ANS rol de procedimentos reference (synthetic).'
AS SELECT
  codigo_tuss,
  nome_procedimento,
  categoria,
  tipo_item,
  segmentacao_cobertura,
  CAST(lower(obrigatorio_rol) = 'true' AS BOOLEAN) AS obrigatorio_rol,
  dut_texto
FROM wks_brabo_demo_catalog.nip_vpp_bronze.bronze_ref_rol_ans;

CREATE OR REFRESH MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_callcenter
COMMENT 'Typed call-center interactions.'
AS SELECT
  interacao_id,
  beneficiario_id,
  to_timestamp(data_interacao) AS data_interacao,
  canal,
  CAST(duracao_seg AS INT)          AS duracao_seg,
  assunto,
  CAST(sentimento_score AS DOUBLE)  AS sentimento_score,
  transcricao,
  CAST(protocolos_abertos AS INT)   AS protocolos_abertos
FROM wks_brabo_demo_catalog.nip_vpp_bronze.bronze_interacoes_callcenter
QUALIFY row_number() OVER (PARTITION BY interacao_id ORDER BY _ingested_at DESC) = 1;
