# Evidence — Unity Catalog governance (LGPD-minded controls)

Applied via `03_unity_catalog/01_governance.sql`. Privilege gated on account group `nip_vpp_admins`
(the running user is **not** a member, so the output below is what a regular analyst sees).

## 1. Column masking on beneficiary PII (`silver_beneficiario`)
```
beneficiario_id | nome         | cpf              | email            | uf
BEN-000002      | Pietro P.    | ***.***.***-47   | ***@example.org  | SP
BEN-000003      | Augusto S.   | ***.***.***-78   | ***@example.net  | RJ
BEN-000006      | Natália G.   | ***.***.***-82   | ***@example.org  | RJ
```
- **cpf** → `***.***.***-NN` (last 2 digits only)
- **email** → local-part masked, domain kept
- **nome** → first name + surname initial

## 2. Row-level security (regional)
`rls_beneficiario(uf)` — admins see all; others see only SP/RJ/MG.
```
ufs_visiveis     = ["MG","RJ","SP"]
linhas_visiveis  = 178   (of 1500 total; the rest are filtered out for non-admins)
```

## 3. Masking propagates to the serving/analyst layer (`gold_nip_queue`)
```
nip_id       | beneficiario_nome | sla_status
MAN-0000020  | Manuela C.        | VENCIDA
MAN-0000028  | Beatriz A.        | VENCIDA
```

## 4. Classification tags (governed tag policy: confidential/restricted/public/internal)
Queried from `information_schema.column_tags`:
```
schema           table                 column            tag           value
nip_vpp_gold     gold_nip_queue        reclamacao_texto  classification confidential
nip_vpp_silver   silver_beneficiario   cpf               classification confidential
nip_vpp_silver   silver_beneficiario   email             classification restricted
nip_vpp_silver   silver_beneficiario   nome              classification restricted
```

## Notes
- Masks + row filter are enforced at query time, so **every** downstream reader (Genie, the app,
  ad-hoc SQL) inherits them — governance is centralized in Unity Catalog, not re-implemented per tool.
- Unity Catalog also captures end-to-end **lineage** automatically (Volume → bronze → silver → gold),
  which was a key ask in the customer conversation. Lineage is visible in the UC UI per table.
