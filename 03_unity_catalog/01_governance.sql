-- ============================================================================
-- GOVERNANCE — LGPD-minded controls on beneficiary PII (health data).
-- Column masking + row-level security + classification tags.
--
-- Privileged access is gated on the account group `nip_vpp_admins`. Members see
-- raw values and all rows; everyone else sees masked PII and a regional subset.
-- NOTE: masks/filters live on the pipeline-managed tables; re-run this script if
-- the Lakeflow pipeline fully refreshes those tables.
-- ============================================================================

-- ---- Masking functions -----------------------------------------------------
CREATE OR REPLACE FUNCTION wks_brabo_demo_catalog.nip_vpp_silver.mask_cpf(cpf STRING)
RETURNS STRING
COMMENT 'Masks CPF to ***.***.***-NN unless caller is a nip_vpp_admins member.'
RETURN CASE WHEN is_account_group_member('nip_vpp_admins') THEN cpf
            ELSE concat('***.***.***-', right(cpf, 2)) END;

CREATE OR REPLACE FUNCTION wks_brabo_demo_catalog.nip_vpp_silver.mask_email(email STRING)
RETURNS STRING
COMMENT 'Masks the local-part of an email, keeps the domain.'
RETURN CASE WHEN is_account_group_member('nip_vpp_admins') THEN email
            ELSE regexp_replace(email, '^[^@]+', '***') END;

CREATE OR REPLACE FUNCTION wks_brabo_demo_catalog.nip_vpp_silver.mask_nome(nome STRING)
RETURNS STRING
COMMENT 'Keeps first name + surname initial for non-privileged callers.'
RETURN CASE WHEN is_account_group_member('nip_vpp_admins') THEN nome
            ELSE concat(split(nome, ' ')[0], ' ',
                        upper(substr(element_at(split(nome, ' '), -1), 1, 1)), '.') END;

-- ---- Row-level security ----------------------------------------------------
CREATE OR REPLACE FUNCTION wks_brabo_demo_catalog.nip_vpp_silver.rls_beneficiario(uf STRING)
RETURNS BOOLEAN
COMMENT 'Regional row filter: admins see all; others see only SP/RJ/MG beneficiaries.'
RETURN is_account_group_member('nip_vpp_admins') OR uf IN ('SP', 'RJ', 'MG');

-- ---- Apply masks + row filter to the beneficiary table ---------------------
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN cpf SET MASK wks_brabo_demo_catalog.nip_vpp_silver.mask_cpf;
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN email SET MASK wks_brabo_demo_catalog.nip_vpp_silver.mask_email;
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN nome SET MASK wks_brabo_demo_catalog.nip_vpp_silver.mask_nome;
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario
  SET ROW FILTER wks_brabo_demo_catalog.nip_vpp_silver.rls_beneficiario ON (uf);

-- Mask the beneficiary name where it surfaces in serving/analyst tables.
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_gold.gold_nip_queue
  ALTER COLUMN beneficiario_nome SET MASK wks_brabo_demo_catalog.nip_vpp_silver.mask_nome;
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_gold.gold_beneficiario_360
  ALTER COLUMN nome SET MASK wks_brabo_demo_catalog.nip_vpp_silver.mask_nome;

-- ---- Classification tags (governed tag policy: confidential/restricted/public/internal) ----
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN cpf   SET TAGS ('classification' = 'confidential');
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN email SET TAGS ('classification' = 'restricted');
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN nome  SET TAGS ('classification' = 'restricted');
ALTER MATERIALIZED VIEW wks_brabo_demo_catalog.nip_vpp_gold.gold_nip_queue
  ALTER COLUMN reclamacao_texto SET TAGS ('classification' = 'confidential');

-- ---- Access model (documented pattern; run manually with the real group) ---
-- In production, analysts get read-only on gold and privileged reviewers join
-- nip_vpp_admins to unmask. Apply with your real group principal, e.g.:
--   GRANT USAGE  ON SCHEMA wks_brabo_demo_catalog.nip_vpp_gold TO `nip_vpp_analysts`;
--   GRANT SELECT ON SCHEMA wks_brabo_demo_catalog.nip_vpp_gold TO `nip_vpp_analysts`;
