-- ============================================================================
-- GOVERNANCE — LGPD-minded controls on beneficiary PII (health data).
-- Column masking + classification tags (enforced), row-level security (shipped).
--
-- Masking is gated on the account group `nip_vpp_admins`: members see raw PII,
-- everyone else sees masked values. Masks/tags are applied directly to both the
-- silver source AND the gold serving columns, so they hold regardless of the
-- order in which the pipeline materializes the views.
--
-- A regional row-filter FUNCTION is shipped (rls_beneficiario) but intentionally
-- NOT applied to silver_beneficiario: an inner-join row filter propagates into the
-- gold serving MVs (nip_queue / beneficiario_360) and would starve the analyst app
-- of NIPs for non-privileged identities. In production it is applied once the app
-- runs under a service principal that belongs to nip_vpp_admins. See the note below.
-- NOTE: re-run this script if the Lakeflow pipeline fully refreshes these tables.
-- ============================================================================

-- ---- Masking functions -----------------------------------------------------
CREATE OR REPLACE FUNCTION wks_demo_brabo_catalog.nip_vpp_silver.mask_cpf(cpf STRING)
RETURNS STRING
COMMENT 'Masks CPF to ***.***.***-NN unless caller is a nip_vpp_admins member.'
RETURN CASE WHEN is_account_group_member('nip_vpp_admins') THEN cpf
            ELSE concat('***.***.***-', right(cpf, 2)) END;

CREATE OR REPLACE FUNCTION wks_demo_brabo_catalog.nip_vpp_silver.mask_email(email STRING)
RETURNS STRING
COMMENT 'Masks the local-part of an email, keeps the domain.'
RETURN CASE WHEN is_account_group_member('nip_vpp_admins') THEN email
            ELSE regexp_replace(email, '^[^@]+', '***') END;

CREATE OR REPLACE FUNCTION wks_demo_brabo_catalog.nip_vpp_silver.mask_nome(nome STRING)
RETURNS STRING
COMMENT 'Keeps first name + surname initial for non-privileged callers.'
RETURN CASE WHEN is_account_group_member('nip_vpp_admins') THEN nome
            ELSE concat(split(nome, ' ')[0], ' ',
                        upper(substr(element_at(split(nome, ' '), -1), 1, 1)), '.') END;

-- ---- Row-level security ----------------------------------------------------
CREATE OR REPLACE FUNCTION wks_demo_brabo_catalog.nip_vpp_silver.rls_beneficiario(uf STRING)
RETURNS BOOLEAN
COMMENT 'Regional row filter: admins see all; others see only SP/RJ/MG beneficiaries.'
RETURN is_account_group_member('nip_vpp_admins') OR uf IN ('SP', 'RJ', 'MG');

-- ---- Apply column masks to the beneficiary table ---------------------------
ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN cpf SET MASK wks_demo_brabo_catalog.nip_vpp_silver.mask_cpf;
ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN email SET MASK wks_demo_brabo_catalog.nip_vpp_silver.mask_email;
ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN nome SET MASK wks_demo_brabo_catalog.nip_vpp_silver.mask_nome;

-- Row filter is shipped above but applied only under a privileged serving identity
-- (see header). To enable regional RLS on direct silver access:
--   ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_silver.silver_beneficiario
--     SET ROW FILTER wks_demo_brabo_catalog.nip_vpp_silver.rls_beneficiario ON (uf);

-- Mask the beneficiary name where it surfaces in serving/analyst tables.
ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_queue
  ALTER COLUMN beneficiario_nome SET MASK wks_demo_brabo_catalog.nip_vpp_silver.mask_nome;
ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_gold.gold_beneficiario_360
  ALTER COLUMN nome SET MASK wks_demo_brabo_catalog.nip_vpp_silver.mask_nome;

-- ---- Classification tags (governed tag policy: confidential/restricted/public/internal) ----
ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN cpf   SET TAGS ('classification' = 'confidential');
ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN email SET TAGS ('classification' = 'restricted');
ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_silver.silver_beneficiario
  ALTER COLUMN nome  SET TAGS ('classification' = 'restricted');
ALTER MATERIALIZED VIEW wks_demo_brabo_catalog.nip_vpp_gold.gold_nip_queue
  ALTER COLUMN reclamacao_texto SET TAGS ('classification' = 'confidential');

-- ---- Access model (documented pattern; run manually with the real group) ---
-- In production, analysts get read-only on gold and privileged reviewers join
-- nip_vpp_admins to unmask. Apply with your real group principal, e.g.:
--   GRANT USAGE  ON SCHEMA wks_demo_brabo_catalog.nip_vpp_gold TO `nip_vpp_analysts`;
--   GRANT SELECT ON SCHEMA wks_demo_brabo_catalog.nip_vpp_gold TO `nip_vpp_analysts`;
