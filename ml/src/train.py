"""Huấn luyện mô hình dự báo rủi ro, log MLflow, đăng ký version và áp quality gate Champion–Challenger.

Cần MLflow server (docker compose up -d postgres mlflow); tracking URI lấy từ MLFLOW_TRACKING_URI,
mặc định http://localhost:5000. Chạy từ gốc repo: .venv\\Scripts\\python ml/src/train.py [--horizon 4]
Chỉ horizon phục vụ hệ thống (h = 4) được đăng ký vào Model Registry; horizon khác chỉ log run để so sánh.
Thiết kế: docs/design/02_9_thiet_ke_giai_thuat.md mục 2.9.2, 2.9.5, 2.9.6.
"""

import argparse
import json
import os
from pathlib import Path

import mlflow
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature

from drift import reference_stats
from gate import MIN_RECALL_CRITICAL, evaluate_risk_gate
from metrics import choose_tau_critical, classification_metrics, scalar_metrics
from risk_models import CV_FOLDS, cross_validate, cross_validate_persistence, fit_balanced, make_candidates
from rpm_common.features import RISK_FEATURE_COLUMNS
from rpm_common.news2 import RISK_CRITICAL
from rpm_common.risk import risk_level_from_proba

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = REPO_ROOT / "ml" / "data" / "processed" / "hourly.parquet"
EXPERIMENT = "risk_forecasting"
REGISTERED_MODEL = "risk_classifier"
SERVING_HORIZON = 4
FEATURES = list(RISK_FEATURE_COLUMNS)


def load_splits(hourly: pd.DataFrame, label: str) -> dict[str, pd.DataFrame]:
    """Mẫu hợp lệ: có nhãn dự báo và giờ hiện tại đủ 5 thông số NEWS2 (để so sánh công bằng với persistence)."""
    samples = hourly[hourly[label].notna() & hourly["risk_class"].notna()].copy()
    # Mọi feature là float để schema MLflow chấp nhận giá trị thiếu lúc suy luận
    samples[FEATURES] = samples[FEATURES].astype(float)
    samples[label] = samples[label].astype(int)
    samples["risk_class"] = samples["risk_class"].astype(int)
    return {name: samples[samples["split"] == name] for name in ("train", "validation", "test")}


def evaluate_champion(client: MlflowClient, test: pd.DataFrame, label: str):
    """Đánh giá lại champion hiện tại trên đúng tập test này; trả (metrics, version) hoặc (None, None) nếu chưa có."""
    try:
        version = client.get_model_version_by_alias(REGISTERED_MODEL, "champion")
    except MlflowException:
        return None, None
    model = mlflow.sklearn.load_model(f"models:/{REGISTERED_MODEL}@champion")
    proba = model.predict_proba(test[FEATURES])
    levels = risk_level_from_proba(proba, float(version.tags["tau_critical"]))
    return classification_metrics(test[label], levels, proba), version.version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--horizon", type=int, default=SERVING_HORIZON)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    client = MlflowClient()
    label = f"label_h{args.horizon}"
    hourly = pd.read_parquet(args.data)
    splits = load_splits(hourly, label)
    train, validation, test = splits["train"], splits["validation"], splits["test"]

    # Chọn họ mô hình bằng GroupKFold trên train ∪ validation
    dev = pd.concat([train, validation])
    candidates = make_candidates(args.seed)
    cv = {name: cross_validate(make, dev[FEATURES], dev[label], dev["subject_id"]) for name, make in candidates.items()}
    cv["persistence"] = cross_validate_persistence(dev["risk_class"], dev[label], dev["subject_id"])
    best = max(candidates, key=lambda name: cv[name]["macro_f1"]["mean"])

    # Huấn luyện trên train, chọn τ_critical trên validation, báo cáo trên test
    model = fit_balanced(candidates[best](), train[FEATURES], train[label])
    val_proba = model.predict_proba(validation[FEATURES])
    tau = choose_tau_critical(validation[label], val_proba[:, RISK_CRITICAL], MIN_RECALL_CRITICAL)
    val_metrics = classification_metrics(validation[label], risk_level_from_proba(val_proba, tau), val_proba)
    test_proba = model.predict_proba(test[FEATURES])
    test_metrics = classification_metrics(test[label], risk_level_from_proba(test_proba, tau), test_proba)
    persistence_test = classification_metrics(test[label], test["risk_class"])

    register = args.horizon == SERVING_HORIZON
    champion, champion_version = evaluate_champion(client, test, label) if register else (None, None)
    gate = evaluate_risk_gate(test_metrics, persistence_test, champion)

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=f"{best}_h{args.horizon}") as run:
        mlflow.log_params(
            {
                "horizon": args.horizon,
                "model": best,
                "estimator": str(model)[:5000],
                "seed": args.seed,
                "tau_critical": tau,
                "target_recall_critical": MIN_RECALL_CRITICAL,
                "cv_folds": CV_FOLDS,
                "n_features": len(FEATURES),
                **{f"n_samples_{name}": len(part) for name, part in splits.items()},
                "champion_compared": champion_version or "none",
            }
        )
        cv_metrics = {
            f"cv_{name}_{metric}_{stat}": value
            for name, result in cv.items()
            for metric, stats in result.items()
            for stat, value in stats.items()
        }
        mlflow.log_metrics(
            cv_metrics
            | scalar_metrics(val_metrics, "val")
            | scalar_metrics(test_metrics, "test")
            | scalar_metrics(persistence_test, "persistence_test")
        )
        evaluation = {
            "validation": val_metrics,
            "test": test_metrics,
            "persistence_test": persistence_test,
            "champion_test": champion,
            "gate": {"passed": gate.passed, "reasons": gate.reasons},
        }
        mlflow.log_dict({"best": best, "cv": cv}, "cv_results.json")
        mlflow.log_dict(evaluation, "evaluation.json")
        mlflow.log_dict({"features": FEATURES, "label": label}, "feature_columns.json")
        mlflow.log_dict(reference_stats(hourly[hourly["split"] == "train"], args.seed), "reference_stats.json")
        mlflow.set_tags({"gate": "passed" if gate.passed else "rejected", "gate_reasons": "; ".join(gate.reasons)})

        version = None
        if register:
            example = train[FEATURES].dropna().head(5)
            info = mlflow.sklearn.log_model(
                model,
                name="model",
                registered_model_name=REGISTERED_MODEL,
                signature=infer_signature(example, model.predict_proba(example)),
                input_example=example,
            )
            version = info.registered_model_version
            tags = {
                "tau_critical": str(tau),
                "horizon": str(args.horizon),
                "model_family": best,
                "gate": "passed" if gate.passed else "rejected",
                "gate_reasons": "; ".join(gate.reasons),
                "trigger": "INITIAL" if champion is None else "MANUAL",
            }
            for key, value in tags.items():
                client.set_model_version_tag(REGISTERED_MODEL, version, key, value)
            client.set_registered_model_alias(REGISTERED_MODEL, "challenger", version)
            if gate.passed:
                client.set_registered_model_alias(REGISTERED_MODEL, "champion", version)

    summary = {
        "run_id": run.info.run_id,
        "best_model": best,
        "tau_critical": tau,
        "cv_macro_f1": {name: round(result["macro_f1"]["mean"], 3) for name, result in cv.items()},
        "test": {k: round(v, 3) for k, v in test_metrics.items() if isinstance(v, float)},
        "persistence_test": {k: round(v, 3) for k, v in persistence_test.items() if isinstance(v, float)},
        "registered_version": version,
        "gate": {"passed": gate.passed, "reasons": gate.reasons},
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
