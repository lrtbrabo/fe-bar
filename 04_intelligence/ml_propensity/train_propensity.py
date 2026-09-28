"""
Train the NIP-propensity model: predict which beneficiaries are likely to open a
NIP, from their call-center behavior (volume, sentiment, protocols). This lets the
operation intervene at the call center BEFORE a complaint escalates to the regulator.

Trains on gold_callcenter_features, logs to MLflow, registers the model to Unity
Catalog, and writes a metrics report as text evidence.

Usage:  python train_propensity.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import mlflow
import pandas as pd
from mlflow.models.signature import infer_signature
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (average_precision_score, classification_report,
                             confusion_matrix, roc_auc_score)
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
from dbx_common import CATALOG, PROFILE, query  # noqa: E402

EVID = Path(__file__).resolve().parents[2] / "evidence"
FEATURES = ["n_interacoes", "avg_sentimento", "min_sentimento", "n_interacoes_negativas",
            "total_protocolos", "avg_duracao_seg", "dias_desde_ultima"]
LABEL = "abriu_nip"
UC_MODEL = f"{CATALOG}.nip_vpp_gold.nip_propensity_model"
EXPERIMENT = "/Users/lucas.brabo@databricks.com/nip_vpp_propensity"


def main():
    os.environ["DATABRICKS_CONFIG_PROFILE"] = PROFILE
    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")
    mlflow.set_experiment(EXPERIMENT)

    rows = query(f"SELECT {', '.join(FEATURES)}, {LABEL} "
                 f"FROM {CATALOG}.nip_vpp_gold.gold_callcenter_features")
    df = pd.DataFrame(rows)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    X, y = df[FEATURES], df[LABEL].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    with mlflow.start_run(run_name="hgb_propensity") as run:
        clf = RandomForestClassifier(
            n_estimators=300, max_depth=6, min_samples_leaf=10,
            class_weight="balanced", random_state=42, n_jobs=-1)
        clf.fit(X_tr, y_tr)

        proba = clf.predict_proba(X_te)[:, 1]
        pred = (proba >= 0.5).astype(int)
        roc = roc_auc_score(y_te, proba)
        pr = average_precision_score(y_te, proba)
        cm = confusion_matrix(y_te, pred)
        report = classification_report(y_te, pred, target_names=["nao_NIP", "abriu_NIP"], digits=3)

        perm = permutation_importance(clf, X_te, y_te, n_repeats=10, random_state=42, scoring="roc_auc")
        importances = sorted(zip(FEATURES, perm.importances_mean), key=lambda t: -t[1])

        mlflow.log_params({"model": "RandomForestClassifier", "n_estimators": 300, "max_depth": 6,
                           "min_samples_leaf": 10, "class_weight": "balanced",
                           "n_features": len(FEATURES), "n_train": len(X_tr), "n_test": len(X_te)})
        mlflow.log_metrics({"roc_auc": roc, "pr_auc": pr,
                            "base_rate": float(y.mean())})
        sig = infer_signature(X_tr, clf.predict_proba(X_tr)[:, 1])
        # RandomForest serializes via skops; its Tree node storage is flagged as
        # "untrusted" by default. We trust it (we trained it), so declare it explicitly.
        mlflow.sklearn.log_model(clf, name="model", signature=sig,
                                 input_example=X_tr.head(3), registered_model_name=UC_MODEL,
                                 skops_trusted_types=["sklearn.tree._tree.Tree"])

        lines = ["# Evidence — NIP-propensity ML model\n",
                 f"Model: `RandomForestClassifier` (class_weight=balanced). "
                 f"Trained on `gold_callcenter_features` ({len(X_tr)} train / {len(X_te)} test). "
                 f"MLflow run `{run.info.run_id}`, registered to UC as `{UC_MODEL}`.\n",
                 f"Base rate (P(opens NIP)) = {y.mean():.1%}. Predicts NIP escalation from "
                 f"call-center behavior so the operation can intervene before a complaint reaches ANS.\n",
                 "## Discrimination",
                 "| Metric | Value |", "|---|---|",
                 f"| ROC-AUC | **{roc:.3f}** |",
                 f"| PR-AUC (avg precision) | **{pr:.3f}** (vs {y.mean():.3f} base rate) |",
                 "\n## Classification report (threshold 0.5)", "```", report, "```",
                 "## Confusion matrix (test)", "```",
                 f"                pred_nao  pred_NIP",
                 f"actual_nao_NIP     {cm[0,0]:>6}   {cm[0,1]:>6}",
                 f"actual_abriu_NIP   {cm[1,0]:>6}   {cm[1,1]:>6}", "```",
                 "## Feature importance (permutation, ROC-AUC drop)", "| Feature | Importance |",
                 "|---|---|"]
        lines += [f"| {f} | {v:.4f} |" for f, v in importances]
        report_md = "\n".join(lines) + "\n"
        EVID.mkdir(exist_ok=True)
        (EVID / "05_ml_propensity.md").write_text(report_md, encoding="utf-8")
        print(report_md)
        print(f"MLflow run: {run.info.run_id}  |  UC model: {UC_MODEL}")


if __name__ == "__main__":
    main()
