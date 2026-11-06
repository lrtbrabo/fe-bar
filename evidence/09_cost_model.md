# Evidence: platform cost vs. return

How much the solution costs to run, **measured** on the prototype's own consumption
(`system.billing.usage` joined with `system.billing.list_prices`, workspace `7474652430122624`,
2026-09-28 → 2026-11-05) and **projected** to production at 2,000 NIPs a month. List prices
(AWS us-east-1), no contract discounts, exchange rate premise **R$ 5,50 per US$**. Implementation
services (the pilot team) are not included.

The workspace also hosts unrelated projects, so only the NIP resources are counted: app
`nip-vpp-copilot`, pipeline `nip_vpp_medallion` (`a92f94d5…`), Lakebase endpoint
`ep-long-dawn-d2w0cbqi`, serving endpoints `nip-propensity` and `databricks-gpt-6-sol`.

## Measured on the prototype

```sql
SELECT billing_origin_product, usage_metadata.*, sum(usage_quantity) AS dbu,
       sum(usage_quantity * lp.pricing.default) AS usd_list
FROM system.billing.usage u JOIN system.billing.list_prices lp USING (sku_name, cloud, usage_unit)
WHERE workspace_id = '7474652430122624' AND <NIP resources> GROUP BY ALL
```

| Resource | Measured | Unit rate |
|---|---|---|
| App `nip-vpp-copilot` (MEDIUM) | 457.3 DBU = **US$ 434.39** in 39 days | 0.50 DBU/h × US$ 0.95 = US$ 0.475/h |
| LLM `databricks-gpt-6-sol` (matcher + parecer) | 10.84 DBU = **US$ 0.76** for the 208-NIP evaluation run | ≤ US$ 0.0037 per NIP |
| Pipeline `nip_vpp_medallion` (serverless) | 0.87 DBU = **US$ 0.39** for 2 triggered updates | ~US$ 0.20 per run |
| Endpoint `nip-propensity` | 2.14 DBU = **US$ 0.15** | scale-to-zero |
| Lakebase `ep-long-dawn-d2w0cbqi` | 298 active hours, **US$ 32.25** | 0.21 DBU/h = US$ 0.111/h at minimum size |
| Lakebase storage (project `e28afa2c…`) | 0.6 DSU = **US$ 0.01** | — |
| SQL warehouse `bb64cb12ed5c77f0` (Small, serverless, shared) | US$ 0.70/DBU | Small = 12 DBU/h = US$ 8.40/h |
| Genie (all spaces of the author, dev usage) | **US$ 167.03** paid + free tier in 22 days | — |

## Projected to production (2,000 NIPs a month)

| Item | Production premise | US$/month | R$/month |
|---|---|---|---|
| SQL warehouse (Genie and app queries) | Small, 10 h/day × 22 days = 220 h | 1,848 | 10,164 |
| App | always on, 730 h | 347 | 1,907 |
| Lakeflow pipeline | hourly (720 runs), ×2 for real data volume | 288 | 1,584 |
| Genie | ~1.5× the author's dev usage, for an analyst team | 250 | 1,375 |
| Lakebase | always on; 4× the minimum size in business hours (220 h), minimum otherwise (510 h) | 154 | 847 |
| LLM matcher + parecer | 2,000 NIPs × US$ 0.0037 | 7 | 41 |
| Propensity model | daily batch scoring | 10 | 55 |
| Storage (Delta + Lakebase) | real volume | 20 | 110 |
| **Total** | | **2,924** | **≈ 16,100** |

## Return

| | Value |
|---|---|
| Platform cost per year | ≈ **R$ 193 mil** (12 × R$ 16,1 mil) |
| Backlog exposure made ready to resolve | **R$ 3,2 mi** (106 overdue NIPs × illustrative R$ 30 mil) |
| Backlog alone vs. one year of platform | **≈ 16×** |
| AI cost per NIP vs. fine per overdue NIP | **≈ R$ 0,02** vs. R$ 30 mil |
| Break-even | avoiding **one overdue NIP every ~2 months** (R$ 16,1 mil ÷ R$ 30 mil = 0.54 NIP/month) |
| Sensitivity: 3× the estimated cost | 1.6 NIP/month, **one every ~3 weeks** |

Not monetized here: the ~560 analyst hours a month freed (2,000 NIPs × 17 min) and the NIPs the
radar prevents. The largest cost line is the warehouse sized for business hours; a smaller size or
a shorter auto-stop lowers it. Prices in the customer's region (sa-east-1) and contract discounts
change the absolute numbers, not the conclusion.
