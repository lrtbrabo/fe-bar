-- Unity Catalog setup for the NIP<->VPP build.
--
-- Ideal layout is a dedicated catalog `nip_vpp`, but this shared FE workspace does not
-- grant CREATE CATALOG on the metastore, so we namespace under an existing catalog with
-- dedicated medallion schemas. Everything downstream references these three schemas.
--
--   Catalog: wks_demo_brabo_catalog
--   Schemas: nip_vpp_bronze / nip_vpp_silver / nip_vpp_gold
--   Landing volume: nip_vpp_bronze.landing
--
-- Governance (masking, row filters, tags, grants) is applied in 01_governance.sql after tables exist.

CREATE SCHEMA IF NOT EXISTS wks_demo_brabo_catalog.nip_vpp_bronze
  COMMENT 'NIP/VPP build — raw ingestion (Auto Loader) from source-system exports.';
CREATE SCHEMA IF NOT EXISTS wks_demo_brabo_catalog.nip_vpp_silver
  COMMENT 'NIP/VPP build — cleaned, typed, deduplicated.';
CREATE SCHEMA IF NOT EXISTS wks_demo_brabo_catalog.nip_vpp_gold
  COMMENT 'NIP/VPP build — analytics- and serving-ready (beneficiary 360, NIP queue, match results).';

CREATE VOLUME IF NOT EXISTS wks_demo_brabo_catalog.nip_vpp_bronze.landing
  COMMENT 'Landing zone for raw source files (manifestacoes, procedimentos, nips, callcenter, dims, rol ANS).';
