# Evidence — Unity Catalog governance (LGPD-minded controls)

Applied via `03_unity_catalog/01_governance.sql` on `wks_demo_brabo_catalog`. Masking is gated on the
account group `nip_vpp_admins` (the running user is **not** a member, so the output below is what a
regular analyst sees).

## 1. Column masking on beneficiary PII (`silver_beneficiario`)
```
beneficiario_id | nome        | cpf              | email
BEN-000001      | Joaquim C.  | ***.***.***-24   | ***@example.net
BEN-000002      | Pietro P.   | ***.***.***-47   | ***@example.org
BEN-000003      | Augusto S.  | ***.***.***-78   | ***@example.net
```
- **cpf** → `***.***.***-NN` (last 2 digits only)
- **email** → local-part masked, domain kept
- **nome** → first name + surname initial

Masks are applied to both the silver source **and** the gold serving columns
(`gold_nip_queue.beneficiario_nome`, `gold_beneficiario_360.nome`), so PII stays masked wherever the
analyst app or Genie reads it.

## 2. Classification tags (governed tag policy: confidential/restricted/public/internal)
Queried from `information_schema.column_tags`:
```
table                 column            classification
gold_nip_queue        reclamacao_texto  confidential
silver_beneficiario   cpf               confidential
silver_beneficiario   email             restricted
silver_beneficiario   nome              restricted
```

## 3. Row-level security (shipped, not applied to the serving path)
`rls_beneficiario(uf)` is defined (admins see all; others see only SP/RJ/MG). It is intentionally
**not** applied to `silver_beneficiario`, because an inner-join row filter propagates into the gold
serving MVs and would starve the analyst app of NIPs for non-privileged identities. In production it
is enabled once the app runs under a service principal in `nip_vpp_admins`. Verified: with the filter
applied, a non-admin saw only 178 of 1500 beneficiaries and the NIP queue collapsed to ~30 of 208.

## Notes
- Masks/tags are enforced at query time, so **every** downstream reader (Genie, the app, ad-hoc SQL)
  inherits them — governance is centralized in Unity Catalog, not re-implemented per tool.
- Unity Catalog also captures end-to-end **lineage** automatically (Volume → bronze → silver → gold),
  a key ask in the customer conversation; visible in the UC UI per table.
