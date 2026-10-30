-- Reset the demo write-back state (analyst decisions + call-center actions) before a rehearsal.
-- Serving tables are untouched. Run with:
--   databricks psql --project nip-vpp -p wks-demo-brabo -- -d databricks_postgres -f 05_lakebase/reset_demo.sql
TRUNCATE nip_vpp.analyst_feedback, nip_vpp.retention_actions RESTART IDENTITY;
