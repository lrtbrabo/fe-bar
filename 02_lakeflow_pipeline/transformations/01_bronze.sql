-- ============================================================================
-- BRONZE — raw ingestion with Auto Loader (streaming tables).
-- Reads the synthetic source exports landed in the UC Volume. All columns kept
-- as strings here (schema stability); typing/cleaning happens in silver.
-- ============================================================================

CREATE OR REFRESH STREAMING TABLE wks_brabo_demo_catalog.nip_vpp_bronze.bronze_manifestacoes
COMMENT 'Raw manifestações (NIP + VPP parent + VPP child) — one table, as in the source.'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/wks_brabo_demo_catalog/nip_vpp_bronze/landing/manifestacoes/',
  format => 'csv', header => true, inferColumnTypes => false, sep => ',');

CREATE OR REFRESH STREAMING TABLE wks_brabo_demo_catalog.nip_vpp_bronze.bronze_procedimentos
COMMENT 'Raw procedure line items for VPP-type manifestações.'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/wks_brabo_demo_catalog/nip_vpp_bronze/landing/procedimentos_solicitados/',
  format => 'csv', header => true, inferColumnTypes => false, sep => ',');

CREATE OR REFRESH STREAMING TABLE wks_brabo_demo_catalog.nip_vpp_bronze.bronze_interacoes_callcenter
COMMENT 'Raw call-center interactions (semi-structured JSONL) — signal for the ML propensity model.'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/wks_brabo_demo_catalog/nip_vpp_bronze/landing/interacoes_callcenter/',
  format => 'json');

CREATE OR REFRESH STREAMING TABLE wks_brabo_demo_catalog.nip_vpp_bronze.bronze_dim_beneficiario
COMMENT 'Raw beneficiary dimension.'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/wks_brabo_demo_catalog/nip_vpp_bronze/landing/dim_beneficiario/',
  format => 'csv', header => true, inferColumnTypes => false, sep => ',');

CREATE OR REFRESH STREAMING TABLE wks_brabo_demo_catalog.nip_vpp_bronze.bronze_dim_plano
COMMENT 'Raw plan dimension.'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/wks_brabo_demo_catalog/nip_vpp_bronze/landing/dim_plano/',
  format => 'csv', header => true, inferColumnTypes => false, sep => ',');

CREATE OR REFRESH STREAMING TABLE wks_brabo_demo_catalog.nip_vpp_bronze.bronze_ref_rol_ans
COMMENT 'Raw ANS rol de procedimentos reference (synthetic).'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/wks_brabo_demo_catalog/nip_vpp_bronze/landing/ref_rol_ans/',
  format => 'csv', header => true, inferColumnTypes => false, sep => ',');

CREATE OR REFRESH STREAMING TABLE wks_brabo_demo_catalog.nip_vpp_bronze.bronze_ground_truth
COMMENT 'Evaluation oracle: the correct VPP manifestação for each NIP (not production data).'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/wks_brabo_demo_catalog/nip_vpp_bronze/landing/ground_truth/',
  format => 'csv', header => true, inferColumnTypes => false, sep => ',');
