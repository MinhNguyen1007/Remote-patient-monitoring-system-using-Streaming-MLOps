"""Tổng hợp kết quả đánh giá cho báo cáo mục 3.4/3.5 → ml/reports/.

Chỉ đọc model `champion` và metric đã log trên MLflow, tính lại trên các tập cố định để lấy bảng/hình.
Không chọn lại ngưỡng hay mô hình nào trên tập test.

Nội dung:
  - mô hình rủi ro: ma trận nhầm lẫn so với persistence, precision/recall theo lớp, SHAP lớp CRITICAL,
    so sánh h = 1 và h = 4 (cần đã chạy `train.py --horizon 1`), lịch sử version;
  - nhãn proxy so với tử vong tại viện (`hospital_expire_flag`) theo đợt ICU;
  - mô hình bất thường: phân phối anomaly_score trên tập test tiêm bất thường, và đối chiếu với diễn biến
    NEWS2 thật (không tiêm) trên mọi cửa sổ của tập test.

Chạy từ gốc repo: .venv\\Scripts\\python ml/src/evaluate.py  (cần MLflow server như train.py)
"""

import tensorflow  # noqa: F401  (nạp DLL TensorFlow trước sklearn/scipy trên Windows)

import argparse
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import shap
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter
from mlflow import MlflowClient
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score

from gate import TAU_ANOMALY
from injection import channel_sigma, inject_anomalies
from metrics import CLASSES, anomaly_metrics, classification_metrics
from rpm_common.anomaly import make_windows
from rpm_common.news2 import RISK_CRITICAL, RISK_LEVELS, RISK_NORMAL
from rpm_common.risk import risk_level_from_proba
from train import EXPERIMENT as RISK_EXPERIMENT
from train import FEATURES, REGISTERED_MODEL as RISK_MODEL, load_splits
from train_anomaly import REGISTERED_MODEL as ANOMALY_MODEL, normal_windows_by_split

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = REPO_ROOT / "ml" / "data" / "processed" / "hourly.parquet"
DEFAULT_OUT = REPO_ROOT / "ml" / "reports"
SHAP_SAMPLE = 400
SEED = 42

# Màu và mực theo bảng tham chiếu của skill dataviz (nền sáng, in trong báo cáo Word)
SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES_1 = "#2a78d6"
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.xaxis.label.set_color(INK_2)
    ax.yaxis.label.set_color(INK_2)


def decimal_comma_x(ax) -> None:
    """Trục x dạng số thập phân kiểu Việt Nam (dấu phẩy)."""
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}".replace(".", ",")))


def new_figure(width: float, height: float, ncols: int = 1):
    fig, axes = plt.subplots(1, ncols, figsize=(width, height), facecolor=SURFACE)
    return fig, axes


def save(fig, path: Path) -> str:
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path.name


# ---------------------------------------------------------------------------------------------- mô hình rủi ro


def plot_confusion(matrices: dict[str, list], path: Path) -> str:
    """Ma trận nhầm lẫn chuẩn hóa theo hàng (tỷ lệ của mỗi lớp thật), cùng thang màu cho mọi panel."""
    cmap = LinearSegmentedColormap.from_list("seq_blue", BLUE_RAMP)
    fig, axes = new_figure(4.4 * len(matrices), 3.9, ncols=len(matrices))
    fig.subplots_adjust(wspace=0.35)
    for index, (ax, (title, matrix)) in enumerate(zip(np.atleast_1d(axes), matrices.items())):
        counts = np.asarray(matrix, dtype=float)
        share = counts / counts.sum(axis=1, keepdims=True)
        ax.imshow(share, cmap=cmap, vmin=0, vmax=1)
        for i in range(len(CLASSES)):
            for j in range(len(CLASSES)):
                ax.text(
                    j, i, f"{int(counts[i, j])}\n{share[i, j]:.0%}", ha="center", va="center", fontsize=9,
                    color="#ffffff" if share[i, j] > 0.5 else INK,
                )
        ax.set_xticks(range(len(CLASSES)), RISK_LEVELS)
        ax.set_yticks(range(len(CLASSES)), RISK_LEVELS)
        ax.set_xlabel("Dự đoán")
        if index == 0:
            ax.set_ylabel("Thực tế (mức cao nhất trong 4 giờ tới)")
        ax.set_title(title, color=INK, fontsize=11, loc="left")
        style_axes(ax)
        for spine in ax.spines.values():
            spine.set_visible(False)
    return save(fig, path)


def per_class_table(y_true, y_pred) -> list[dict]:
    precision, recall, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=CLASSES, zero_division=0)
    return [
        {"class": RISK_LEVELS[c], "precision": precision[c], "recall": recall[c], "f1": f1[c], "support": int(support[c])}
        for c in CLASSES
    ]


def shap_critical(model, X: pd.DataFrame, path: Path) -> tuple[list[dict], str]:
    """Mean |SHAP| cho lớp CRITICAL trên một mẫu tập test (pipeline: SimpleImputer → RandomForest)."""
    imputer, forest = model.steps[0][1], model.steps[-1][1]
    sample = X.sample(n=min(SHAP_SAMPLE, len(X)), random_state=SEED)
    imputed = pd.DataFrame(imputer.transform(sample), columns=FEATURES, index=sample.index)
    values = shap.TreeExplainer(forest).shap_values(imputed)
    critical = values[:, :, RISK_CRITICAL] if np.ndim(values) == 3 else values[RISK_CRITICAL]
    importance = pd.Series(np.abs(critical).mean(axis=0), index=FEATURES).sort_values(ascending=False)
    # Hướng tác động: tương quan giữa giá trị đặc trưng và SHAP (dương = giá trị cao đẩy P(CRITICAL) lên)
    direction = {
        f: float(np.corrcoef(imputed[f], critical[:, i])[0, 1]) if imputed[f].std() > 0 else 0.0
        for i, f in enumerate(FEATURES)
    }

    top = importance.head(15)[::-1]
    fig, ax = new_figure(6.4, 5.2)
    ax.barh(top.index, top.values, color=SERIES_1, height=0.6)
    ax.set_xlabel("Trung bình |SHAP| của P(CRITICAL)")
    decimal_comma_x(ax)
    ax.set_title("15 đặc trưng ảnh hưởng nhất tới dự báo CRITICAL", color=INK, fontsize=11, loc="left")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    style_axes(ax)
    table = [
        {"feature": f, "mean_abs_shap": float(v), "direction": direction[f]} for f, v in importance.head(15).items()
    ]
    return table, save(fig, path)


def latest_run_for_horizon(client: MlflowClient, horizon: int):
    experiment = client.get_experiment_by_name(RISK_EXPERIMENT)
    runs = client.search_runs(
        [experiment.experiment_id], f"params.horizon = '{horizon}'", order_by=["attributes.start_time DESC"], max_results=1
    )
    return runs[0] if runs else None


def risk_section(client: MlflowClient, hourly: pd.DataFrame, out: Path) -> dict:
    version = client.get_model_version_by_alias(RISK_MODEL, "champion")
    tau = float(version.tags["tau_critical"])
    model = mlflow.sklearn.load_model(f"models:/{RISK_MODEL}@champion")
    test = load_splits(hourly, "label_h4")["test"]
    proba = model.predict_proba(test[FEATURES])
    levels = risk_level_from_proba(proba, tau)
    model_metrics = classification_metrics(test["label_h4"], levels, proba)
    persistence = classification_metrics(test["label_h4"], test["risk_class"])

    confusion_png = plot_confusion(
        {
            f"Random Forest (τ_critical = {fmt(tau, 2)})": model_metrics["confusion_matrix"],
            "Baseline persistence": persistence["confusion_matrix"],
        },
        out / "fig_risk_confusion.png",
    )
    shap_table, shap_png = shap_critical(model, test[FEATURES], out / "fig_risk_shap_critical.png")

    horizons = {}
    for horizon in (1, 4):
        run = client.get_run(version.run_id) if horizon == 4 else latest_run_for_horizon(client, horizon)
        if run is None:
            continue
        evaluation = mlflow.artifacts.load_dict(f"runs:/{run.info.run_id}/evaluation.json")
        horizons[horizon] = {
            "run_id": run.info.run_id,
            "tau_critical": float(run.data.params["tau_critical"]),
            "model": {k: evaluation["test"][k] for k in ("macro_f1", "recall_critical", "precision_critical", "auroc_ovr")},
            "persistence": {k: evaluation["persistence_test"][k] for k in ("macro_f1", "recall_critical", "precision_critical")},
        }

    history = []
    for found in sorted(client.search_model_versions(f"name = '{RISK_MODEL}'"), key=lambda v: int(v.version)):
        # search_model_versions không trả alias → đọc lại từng version
        mv = client.get_model_version(RISK_MODEL, found.version)
        metrics = client.get_run(mv.run_id).data.metrics
        history.append(
            {
                "version": int(mv.version),
                "tau_critical": float(mv.tags.get("tau_critical", "nan")),
                "tau_selection": mv.tags.get("tau_selection", "validation"),
                "test_macro_f1": metrics.get("test_macro_f1"),
                "test_recall_critical": metrics.get("test_recall_critical"),
                "gate": mv.tags.get("gate"),
                "champion": "champion" in mv.aliases,
            }
        )

    return {
        "champion_version": int(version.version),
        "tau_critical": tau,
        "n_test_samples": int(len(test)),
        "test": model_metrics,
        "persistence_test": persistence,
        "per_class": {"model": per_class_table(test["label_h4"], levels), "persistence": per_class_table(test["label_h4"], test["risk_class"])},
        "shap_critical_top15": shap_table,
        "horizons": horizons,
        "versions": history,
        "figures": [confusion_png, shap_png],
    }


# ------------------------------------------------------------------------------------------------ nhãn proxy


def proxy_section(hourly: pd.DataFrame) -> dict:
    """Tỷ lệ giờ CRITICAL của mỗi đợt ICU theo kết cục tử vong tại viện (toàn bộ dữ liệu, không dùng model)."""
    rated = hourly[hourly["risk_class"].notna()]
    stays = rated.groupby("icustay_id").agg(
        critical_share=("risk_class", lambda s: float((s == RISK_CRITICAL).mean())),
        died=("hospital_expire_flag", "first"),
        subject_id=("subject_id", "first"),
    )
    groups = {}
    for died, part in stays.groupby("died"):
        groups["died" if died == 1 else "survived"] = {
            "n_stays": int(len(part)),
            "n_subjects": int(part["subject_id"].nunique()),
            "mean_critical_share": float(part["critical_share"].mean()),
            "median_critical_share": float(part["critical_share"].median()),
        }
    return {
        "groups": groups,
        # AUROC mức đợt ICU: tỷ lệ giờ CRITICAL phân biệt đợt tử vong tại viện với đợt sống sót
        "stay_auroc": float(roc_auc_score(stays["died"], stays["critical_share"])),
    }


# ---------------------------------------------------------------------------------------------- mô hình bất thường


def plot_anomaly_scores(groups: dict[str, np.ndarray], path: Path) -> str:
    fig, ax = new_figure(6.4, 3.4)
    names = list(groups)[::-1]
    data = [groups[n] for n in names]
    ax.boxplot(
        data, vert=False, widths=0.5, showfliers=False, patch_artist=True,
        boxprops={"facecolor": "#cde2fb", "edgecolor": SERIES_1, "linewidth": 1.2},
        medianprops={"color": INK, "linewidth": 1.5},
        whiskerprops={"color": SERIES_1}, capprops={"color": SERIES_1},
    )
    rng = np.random.default_rng(SEED)
    for i, values in enumerate(data, start=1):
        ax.scatter(
            values, i + rng.uniform(-0.15, 0.15, len(values)), s=8, color=INK_2, alpha=0.35, linewidths=0, zorder=3
        )
    ax.axvline(TAU_ANOMALY, color=INK, linestyle="--", linewidth=1)
    ax.text(
        TAU_ANOMALY - 0.01, len(data) + 0.45, f"τ_anomaly = {fmt(TAU_ANOMALY, 2)}", ha="right", va="bottom",
        fontsize=8, color=INK_2,
    )
    ax.set_yticks(range(1, len(data) + 1), [f"{n} (n = {len(groups[n])})" for n in names])
    ax.set_xlim(0, 1.02)
    decimal_comma_x(ax)
    ax.set_xlabel("anomaly_score")
    ax.set_title("anomaly_score trên tập test đã tiêm bất thường", color=INK, fontsize=11, loc="left")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    style_axes(ax)
    return save(fig, path)


def anomaly_section(client: MlflowClient, hourly: pd.DataFrame, out: Path) -> dict:
    version = client.get_model_version_by_alias(ANOMALY_MODEL, "champion")
    detector = mlflow.pyfunc.load_model(f"models:/{ANOMALY_MODEL}@champion")
    normal = normal_windows_by_split(hourly)
    sigma = channel_sigma(normal["train"])
    injected, is_anomaly, kind = inject_anomalies(normal["test"], sigma)
    scores = detector.predict(injected)
    labels = {"": "Không tiêm", "spike": "Spike", "level_shift": "Level shift", "drift": "Drift dần"}
    figure = plot_anomaly_scores({labels[k]: scores[kind == k] for k in labels}, out / "fig_anomaly_scores.png")

    # Đối chiếu với diễn biến thật: mọi cửa sổ (không tiêm) của tập test, nhóm theo mức NEWS2 cao nhất trong 12 giờ
    windows, meta = make_windows(hourly)
    is_test = (hourly.loc[meta["row"], "split"] == "test").to_numpy()
    test_windows, test_meta = windows[is_test], meta[is_test].reset_index(drop=True)
    window_max = hourly.groupby("icustay_id")["risk_class"].transform(lambda s: s.rolling(12, min_periods=1).max())
    worst = window_max.loc[test_meta["row"]].to_numpy()
    real_scores = detector.predict(test_windows)
    by_level = {}
    for level in CLASSES:
        part = real_scores[worst == level]
        by_level[RISK_LEVELS[level]] = {
            "n_windows": int(len(part)),
            "median_score": float(np.median(part)) if len(part) else None,
            "flag_rate": float((part >= TAU_ANOMALY).mean()) if len(part) else None,
        }
    has_critical = worst == RISK_CRITICAL
    all_normal = worst == RISK_NORMAL
    keep = has_critical | all_normal

    return {
        "champion_version": int(version.version),
        "test_injected": anomaly_metrics(is_anomaly, scores, TAU_ANOMALY, kind),
        "real_windows_by_worst_news2": by_level,
        # AUROC: anomaly_score phân biệt cửa sổ có ít nhất 1 giờ CRITICAL với cửa sổ toàn NORMAL (dữ liệu thật)
        "real_auroc_critical_vs_normal": float(roc_auc_score(has_critical[keep], real_scores[keep])),
        "figures": [figure],
    }


# ---------------------------------------------------------------------------------------------- báo cáo markdown


def fmt(value, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}".replace(".", ",")


def pct(value) -> str:
    return "—" if value is None else f"{100 * value:.1f}%".replace(".", ",")


def write_markdown(summary: dict, path: Path) -> None:
    risk, proxy, anomaly = summary["risk"], summary["proxy_label"], summary["anomaly"]
    lines = [
        "# Kết quả đánh giá mô hình (sinh tự động bởi `ml/src/evaluate.py`)",
        "",
        "Mọi chỉ số đo trên nhóm `test` cố định (15 bệnh nhân), trừ khi ghi khác. Không chọn lại ngưỡng hay mô hình nào trên tập test.",
        "",
        f"## 1. Dự báo rủi ro (h = 4) — `{RISK_MODEL}` v{risk['champion_version']}, τ_critical = {fmt(risk['tau_critical'], 2)}",
        "",
        f"{risk['n_test_samples']} mẫu giờ. ![Ma trận nhầm lẫn]({risk['figures'][0]})",
        "",
        "| Chỉ số | Random Forest | Persistence |",
        "|---|---|---|",
    ]
    for key, name in [("accuracy", "Accuracy"), ("macro_f1", "Macro F1"), ("recall_critical", "Recall CRITICAL"),
                      ("precision_critical", "Precision CRITICAL"), ("auroc_ovr", "AUROC (OvR, macro)"),
                      ("auprc_critical", "AUPRC CRITICAL")]:
        lines.append(f"| {name} | {fmt(risk['test'].get(key))} | {fmt(risk['persistence_test'].get(key))} |")
    lines += ["", "Theo từng lớp:", "", "| Lớp | Số mẫu | Precision (model / persistence) | Recall (model / persistence) | F1 (model / persistence) |", "|---|---|---|---|---|"]
    for m, p in zip(risk["per_class"]["model"], risk["per_class"]["persistence"]):
        lines.append(
            f"| {m['class']} | {m['support']} | {fmt(m['precision'])} / {fmt(p['precision'])} | "
            f"{fmt(m['recall'])} / {fmt(p['recall'])} | {fmt(m['f1'])} / {fmt(p['f1'])} |"
        )
    lines += ["", "### So sánh horizon", "", "| Horizon | τ_critical | Macro F1 model | Macro F1 persistence | Recall CRITICAL model | Recall CRITICAL persistence | Precision CRITICAL model |", "|---|---|---|---|---|---|---|"]
    for horizon, h in sorted(risk["horizons"].items()):
        lines.append(
            f"| h = {horizon} | {fmt(h['tau_critical'], 2)} | {fmt(h['model']['macro_f1'])} | {fmt(h['persistence']['macro_f1'])} | "
            f"{fmt(h['model']['recall_critical'])} | {fmt(h['persistence']['recall_critical'])} | {fmt(h['model']['precision_critical'])} |"
        )
    lines += ["", f"### Giải thích mô hình (SHAP, lớp CRITICAL, {SHAP_SAMPLE} mẫu test)", "", f"![SHAP]({risk['figures'][1]})", "",
              "| Đặc trưng | Mean \\|SHAP\\| | Hướng (tương quan giá trị–SHAP) |", "|---|---|---|"]
    for row in risk["shap_critical_top15"]:
        lines.append(f"| `{row['feature']}` | {fmt(row['mean_abs_shap'], 4)} | {fmt(row['direction'], 2)} |")
    lines += ["", "### Lịch sử version", "", "| Version | τ_critical | Cách chọn τ | Macro F1 test | Recall CRITICAL test | Gate | Champion |", "|---|---|---|---|---|---|---|"]
    for v in risk["versions"]:
        lines.append(
            f"| v{v['version']} | {fmt(v['tau_critical'], 2)} | {v['tau_selection']} | {fmt(v['test_macro_f1'])} | "
            f"{fmt(v['test_recall_critical'])} | {v['gate']} | {'✓' if v['champion'] else ''} |"
        )
    lines += ["", "## 2. Nhãn proxy (NEWS2) so với tử vong tại viện", "",
              "Toàn bộ dữ liệu, mức đợt ICU. Cả 100 bệnh nhân của bản Demo về sau đều tử vong (thiên lệch chọn mẫu, mục 3.5).", "",
              "| Kết cục lượt nhập viện | Số đợt ICU | Số bệnh nhân | Tỷ lệ giờ CRITICAL (trung bình) | (trung vị) |", "|---|---|---|---|---|"]
    for name, label in [("died", "Tử vong tại viện"), ("survived", "Sống sót ra viện")]:
        g = proxy["groups"][name]
        lines.append(f"| {label} | {g['n_stays']} | {g['n_subjects']} | {pct(g['mean_critical_share'])} | {pct(g['median_critical_share'])} |")
    lines += ["", f"AUROC mức đợt ICU của tỷ lệ giờ CRITICAL khi phân biệt tử vong/sống sót: {fmt(proxy['stay_auroc'])}.", "",
              f"## 3. Phát hiện bất thường — `{ANOMALY_MODEL}` v{anomaly['champion_version']}, τ_anomaly = {fmt(TAU_ANOMALY, 2)}", "",
              f"![anomaly_score]({anomaly['figures'][0]})", "", "Tập test tiêm bất thường (10% cửa sổ NORMAL, seed 42):", "",
              "| Chỉ số | Giá trị |", "|---|---|"]
    t = anomaly["test_injected"]
    for key, name in [("auroc", "AUROC (tiêu chí gate)"), ("precision", "Precision"), ("recall", "Recall"), ("f1", "F1"),
                      ("false_positive_rate", "Tỷ lệ gắn cờ nhầm"), ("recall_spike", "Recall spike"),
                      ("recall_level_shift", "Recall level shift"), ("recall_drift", "Recall drift dần")]:
        lines.append(f"| {name} | {fmt(t.get(key))} |")
    lines += ["", f"Số cửa sổ: {t['n_windows']}, trong đó {t['n_anomalies']} bị tiêm.", "",
              "Đối chiếu với diễn biến thật (mọi cửa sổ của tập test, không tiêm), nhóm theo mức NEWS2 cao nhất trong 12 giờ:", "",
              "| Mức cao nhất trong cửa sổ | Số cửa sổ | Trung vị anomaly_score | Tỷ lệ bị gắn cờ |", "|---|---|---|---|"]
    for level, row in anomaly["real_windows_by_worst_news2"].items():
        lines.append(f"| {level} | {row['n_windows']} | {fmt(row['median_score'])} | {pct(row['flag_rate'])} |")
    lines += ["", f"AUROC của anomaly_score khi phân biệt cửa sổ có giờ CRITICAL với cửa sổ toàn NORMAL: {fmt(anomaly['real_auroc_critical_vs_normal'])}.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    client = MlflowClient()
    args.out.mkdir(parents=True, exist_ok=True)
    hourly = pd.read_parquet(args.data)

    summary = {
        "risk": risk_section(client, hourly, args.out),
        "proxy_label": proxy_section(hourly),
        "anomaly": anomaly_section(client, hourly, args.out),
    }
    (args.out / "evaluation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=float), encoding="utf-8"
    )
    write_markdown(summary, args.out / "evaluation.md")
    print(f"Đã ghi {args.out}")


if __name__ == "__main__":
    main()
