# Evidence — NIP-propensity ML model

Model: `RandomForestClassifier` (class_weight=balanced). Trained on `gold_callcenter_features` (1125 train / 375 test). MLflow run `987051eab3184114b5cc023f82ca8210`, registered to UC as `wks_demo_brabo_catalog.nip_vpp_gold.nip_propensity_model`.

Base rate (P(opens NIP)) = 13.9%. Predicts NIP escalation from call-center behavior so the operation can intervene before a complaint reaches ANS.

## Discrimination
| Metric | Value |
|---|---|
| ROC-AUC | **0.926** |
| PR-AUC (avg precision) | **0.840** (vs 0.139 base rate) |

## Classification report (threshold 0.5)
```
              precision    recall  f1-score   support

     nao_NIP      0.963     0.966     0.964       323
   abriu_NIP      0.784     0.769     0.777        52

    accuracy                          0.939       375
   macro avg      0.874     0.868     0.871       375
weighted avg      0.938     0.939     0.938       375

```
## Confusion matrix (test)
```
                pred_nao  pred_NIP
actual_nao_NIP        312       11
actual_abriu_NIP       12       40
```
## Feature importance (permutation, ROC-AUC drop)
| Feature | Importance |
|---|---|
| total_protocolos | 0.0441 |
| avg_sentimento | 0.0439 |
| min_sentimento | 0.0126 |
| n_interacoes | 0.0058 |
| n_interacoes_negativas | 0.0004 |
| avg_duracao_seg | -0.0040 |
| dias_desde_ultima | -0.0062 |

## Deployed to Model Serving
Registered model deployed to serving endpoint **`nip-propensity`** (scale-to-zero). Live test via
`/serving-endpoints/nip-propensity/invocations`:
```
input  (high-risk): 5 interactions, avg_sentimento -0.6, 4 negatives, 3 protocols  -> prediction 1 (will open NIP)
input  (low-risk):  1 interaction,  avg_sentimento +0.5, 0 negatives, 0 protocols  -> prediction 0
output: {"predictions": [1, 0]}
```
The operation can score beneficiaries in real time and intervene at the call center before a NIP is filed.

## Batch scoring for the Radar (`04_intelligence/ml_propensity/score_propensity.py`)
All 1,500 beneficiaries scored with UC model version 3 (`predict_proba`), published to
`gold_propensity_scores` with plain-language drivers, and reverse-ETL'd to Lakebase `nip_vpp.propensity`.
```
scored 1500 beneficiaries; without NIP: 1292
faixa_risco (without NIP): BAIXO 1225 · MEDIO 58 · ALTO 9
top: BEN-001396 0.81  2 protocolos abertos; sentimento médio -0,23
     BEN-000273 0.80  3 protocolos abertos; 2 contatos negativos; 5 contatos com o call center
     BEN-000771 0.79  sentimento médio -0,40
```
Scores for beneficiaries that were in the training split are in-sample; the out-of-sample figure quoted in
the app (recall 77%, 40 of 52 NIP-openers) is the test-split result above.
