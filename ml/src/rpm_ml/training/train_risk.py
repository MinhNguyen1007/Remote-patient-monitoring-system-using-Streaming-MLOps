"""Huấn luyện mô hình dự báo rủi ro, log MLflow, đăng ký version và áp quality gate Champion–Challenger.

Cần MLflow server (docker compose up -d postgres mlflow); tracking URI lấy từ MLFLOW_TRACKING_URI,
mặc định http://localhost:5000. Chạy: python -m rpm_ml.training.train_risk [--horizon 4]
Chỉ horizon phục vụ hệ thống (h = 4) được đăng ký vào Model Registry; horizon khác chỉ log run để so sánh.
DAG retrain_pipeline gọi `train_risk_model` qua rpm_ml.pipelines.retrain với nhóm huấn luyện train + stream.
Thiết kế: docs/design/02_9_thiet_ke_giai_thuat.md mục 2.9.2, 2.9.4, 2.9.5, 2.9.6.
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

from rpm_ml.paths import HOURLY_FILE
from rpm_ml.drift.stats import calibrate_thresholds, reference_stats
from rpm_ml.evaluation.gate import TARGET_RECALL_CRITICAL, evaluate_risk_gate
from rpm_ml.evaluation.metrics import choose_tau_critical, classification_metrics, scalar_metrics
from rpm_ml.models.risk import CV_FOLDS, cross_validate, cross_validate_persistence, fit_balanced, make_candidates
from rpm_common.features import RISK_FEATURE_COLUMNS
from rpm_common.news2 import RISK_CRITICAL
from rpm_common.risk import risk_level_from_proba

DEFAULT_DATA = HOURLY_FILE
EXPERIMENT = "risk_forecasting"
REGISTERED_MODEL = "risk_classifier"
SERVING_HORIZON = 4
FEATURES = list(RISK_FEATURE_COLUMNS)
TAU_SELECTION = "oof_groupkfold_train_validation"
INITIAL_TRAINING_GROUPS = ("train",)


def load_splits(
    hourly: pd.DataFrame, label: str, training_groups: tuple[str, ...] = INITIAL_TRAINING_GROUPS
) -> dict[str, pd.DataFrame]:
    """Mẫu hợp lệ: có nhãn dự báo và giờ hiện tại đủ 5 thông số NEWS2 (để so sánh công bằng với persistence).

    "train" gồm mọi nhóm trong `training_groups` (retrain thêm "stream"); validation và test không bao giờ đổi.
    """
    samples = hourly[hourly[label].notna() & hourly["risk_class"].notna()].copy()
    # Mọi feature là float để schema MLflow chấp nhận giá trị thiếu lúc suy luận
    samples[FEATURES] = samples[FEATURES].astype(float)
    samples[label] = samples[label].astype(int)
    samples["risk_class"] = samples["risk_class"].astype(int)
    return {
        "train": samples[samples["split"].isin(training_groups)],
        "validation": samples[samples["split"] == "validation"],
        "test": samples[samples["split"] == "test"],
    }


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


def rounded(metrics: dict | None) -> dict | None:
    return None if metrics is None else {k: round(v, 3) for k, v in metrics.items() if isinstance(v, float)}


def train_risk_model(
    hourly: pd.DataFrame,
    *,
    horizon: int = SERVING_HORIZON,
    seed: int = 42,
    training_groups: tuple[str, ...] = INITIAL_TRAINING_GROUPS,
    trigger: str | None = None,
    tags: dict[str, str] | None = None,
) -> dict:
    """Chọn họ mô hình + τ_critical, huấn luyện, đánh giá cùng champion trên test cố định, áp gate, log/đăng ký MLflow.

    `trigger` = INITIAL/MANUAL/DRIFT (mặc định: INITIAL khi chưa có champion, ngược lại MANUAL). `tags` gắn thêm cho
    run và version (vd dag_run_id, drift_report_id). Trả về tóm tắt gồm version đã đăng ký và kết quả gate.
    """
    client = MlflowClient()
    label = f"label_h{horizon}"
    splits = load_splits(hourly, label, training_groups)
    train, validation, test = splits["train"], splits["validation"], splits["test"]
    training_rows = hourly[hourly["split"].isin(training_groups)]

    # Chọn họ mô hình bằng GroupKFold trên (nhóm huấn luyện) ∪ validation
    dev = pd.concat([train, validation])
    candidates = make_candidates(seed)
    cv, oof_proba = {}, {}
    for name, make in candidates.items():
        cv[name], oof_proba[name] = cross_validate(make, dev[FEATURES], dev[label], dev["subject_id"])
    cv["persistence"] = cross_validate_persistence(dev["risk_class"], dev[label], dev["subject_id"])
    best = max(candidates, key=lambda name: cv[name]["macro_f1"]["mean"])

    # Chọn τ_critical trên dự đoán out-of-fold của họ mô hình thắng (nhiều bệnh nhân hơn hẳn riêng validation)
    tau = choose_tau_critical(dev[label], oof_proba[best][:, RISK_CRITICAL], TARGET_RECALL_CRITICAL)
    oof_metrics = classification_metrics(
        dev[label], risk_level_from_proba(oof_proba[best], tau), oof_proba[best]
    )

    # Model cuối huấn luyện trên nhóm huấn luyện; validation chưa được model này thấy nên vẫn là tập kiểm tra độc lập
    model = fit_balanced(candidates[best](), train[FEATURES], train[label])
    val_proba = model.predict_proba(validation[FEATURES])
    val_metrics = classification_metrics(validation[label], risk_level_from_proba(val_proba, tau), val_proba)
    test_proba = model.predict_proba(test[FEATURES])
    test_metrics = classification_metrics(test[label], risk_level_from_proba(test_proba, tau), test_proba)
    persistence_test = classification_metrics(test[label], test["risk_class"])

    register = horizon == SERVING_HORIZON
    champion, champion_version = evaluate_champion(client, test, label) if register else (None, None)
    gate = evaluate_risk_gate(test_metrics, persistence_test, champion)
    trigger = trigger or ("INITIAL" if champion is None else "MANUAL")
    # Tham chiếu drift = dữ liệu huấn luyện của chính model này; ngưỡng hiệu chỉnh trên dữ liệu phát triển (không có test)
    drift_calibration = (
        calibrate_thresholds(pd.concat([training_rows, hourly[hourly["split"] == "validation"]]), seed)
        if register
        else None
    )

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=f"{best}_h{horizon}") as run:
        mlflow.log_params(
            {
                "horizon": horizon,
                "model": best,
                "estimator": str(model)[:5000],
                "seed": seed,
                "tau_critical": tau,
                "tau_selection": TAU_SELECTION,
                "target_recall_critical": TARGET_RECALL_CRITICAL,
                "cv_folds": CV_FOLDS,
                "n_features": len(FEATURES),
                "training_groups": ",".join(training_groups),
                **{f"n_samples_{name}": len(part) for name, part in splits.items()},
                **{f"n_hours_{group}": int((training_rows["split"] == group).sum()) for group in training_groups},
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
            | scalar_metrics(oof_metrics, "oof")
            | scalar_metrics(val_metrics, "val")
            | scalar_metrics(test_metrics, "test")
            | scalar_metrics(persistence_test, "persistence_test")
        )
        evaluation = {
            "out_of_fold": oof_metrics,
            "validation": val_metrics,
            "test": test_metrics,
            "persistence_test": persistence_test,
            "champion_test": champion,
            "gate": {"passed": gate.passed, "reasons": gate.reasons},
        }
        mlflow.log_dict({"best": best, "cv": cv}, "cv_results.json")
        mlflow.log_dict(evaluation, "evaluation.json")
        mlflow.log_dict({"features": FEATURES, "label": label}, "feature_columns.json")
        mlflow.log_dict(reference_stats(training_rows, seed), "reference_stats.json")
        if drift_calibration is not None:
            mlflow.log_dict(drift_calibration, "drift_thresholds.json")
        mlflow.set_tags(
            {"gate": "passed" if gate.passed else "rejected", "gate_reasons": "; ".join(gate.reasons), "trigger": trigger}
            | (tags or {})
        )

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
            version_tags = {
                "tau_critical": str(tau),
                "tau_selection": TAU_SELECTION,
                "horizon": str(horizon),
                "model_family": best,
                "gate": "passed" if gate.passed else "rejected",
                "gate_reasons": "; ".join(gate.reasons),
                "trigger": trigger,
                "training_groups": ",".join(training_groups),
            } | (tags or {})
            for key, value in version_tags.items():
                client.set_model_version_tag(REGISTERED_MODEL, version, key, value)
            client.set_registered_model_alias(REGISTERED_MODEL, "challenger", version)
            if gate.passed:
                client.set_registered_model_alias(REGISTERED_MODEL, "champion", version)

    return {
        "model_name": REGISTERED_MODEL,
        "run_id": run.info.run_id,
        "best_model": best,
        "tau_critical": tau,
        "training_groups": list(training_groups),
        "n_samples": {name: len(part) for name, part in splits.items()},
        "cv_macro_f1": {name: round(result["macro_f1"]["mean"], 3) for name, result in cv.items()},
        "out_of_fold": rounded(oof_metrics),
        "validation": rounded(val_metrics),
        "test": rounded(test_metrics),
        "persistence_test": rounded(persistence_test),
        "champion_version": champion_version,
        "champion_test": rounded(champion),
        "drift_thresholds": None if drift_calibration is None else drift_calibration["thresholds"],
        "registered_version": version,
        "trigger": trigger,
        "gate": {"passed": gate.passed, "reasons": gate.reasons},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--horizon", type=int, default=SERVING_HORIZON)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    summary = train_risk_model(pd.read_parquet(args.data), horizon=args.horizon, seed=args.seed)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
