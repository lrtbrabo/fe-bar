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
