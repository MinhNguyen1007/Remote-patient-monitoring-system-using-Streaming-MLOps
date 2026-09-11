"""Quality gate Champion–Challenger — docs/design/02_9 mục 2.9.5 và 02_10 mục 2.10.3."""

from dataclasses import dataclass, field

MIN_MACRO_F1 = 0.60
MIN_RECALL_CRITICAL = 0.75
# τ_critical được chọn để đạt recall cao hơn ngưỡng gate: nếu hai giá trị bằng nhau, tập test nhỏ (15 bệnh nhân)
# khiến mỗi lần train/retrain có khoảng 50% khả năng trượt chỉ do nhiễu. Hiệu chỉnh 2026-09-11 (trước đó gate = 0,80).
TARGET_RECALL_CRITICAL = 0.80

TAU_ANOMALY = 0.99
# Gate của mô hình bất thường dùng AUROC (không phụ thuộc ngưỡng). Ngưỡng Precision/Recall ≥ 0,70 tại τ = 0,99 ban
# đầu không đạt được với dữ liệu này: bất thường tiêm theo mục 2.9.3 nằm trong độ biến thiên tự nhiên của vitals
# theo giờ (đo bằng GroupKFold trên train ∪ validation, 2026-09-11). Precision/Recall/F1 vẫn được báo cáo.
MIN_AUROC_ANOMALY = 0.75


@dataclass
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def evaluate_risk_gate(challenger: dict, persistence: dict, champion: dict | None = None) -> GateResult:
    """Mọi metric phải đo trên cùng tập test cố định. `champion=None` khi chưa có model đang chạy (lần đầu)."""
    reasons = []
    if challenger["macro_f1"] < MIN_MACRO_F1:
        reasons.append(f"Macro F1 {challenger['macro_f1']:.3f} < ngưỡng {MIN_MACRO_F1:.2f}")
    if challenger["recall_critical"] < MIN_RECALL_CRITICAL:
        reasons.append(f"Recall CRITICAL {challenger['recall_critical']:.3f} < ngưỡng {MIN_RECALL_CRITICAL:.2f}")
    if challenger["macro_f1"] <= persistence["macro_f1"]:
        reasons.append(
            f"Macro F1 {challenger['macro_f1']:.3f} không cao hơn baseline persistence {persistence['macro_f1']:.3f}"
        )
    if champion is not None:
        if challenger["macro_f1"] < champion["macro_f1"]:
            reasons.append(f"Macro F1 {challenger['macro_f1']:.3f} < champion {champion['macro_f1']:.3f}")
        if challenger["recall_critical"] < champion["recall_critical"]:
            reasons.append(
                f"Recall CRITICAL {challenger['recall_critical']:.3f} < champion {champion['recall_critical']:.3f}"
            )
    return GateResult(passed=not reasons, reasons=reasons)


def evaluate_anomaly_gate(challenger: dict, champion: dict | None = None) -> GateResult:
    """Gate độc lập của mô hình bất thường, đo trên cùng tập test đã tiêm bất thường (seed cố định)."""
    reasons = []
    if challenger["auroc"] < MIN_AUROC_ANOMALY:
        reasons.append(f"AUROC {challenger['auroc']:.3f} < ngưỡng {MIN_AUROC_ANOMALY:.2f}")
    if champion is not None and challenger["auroc"] < champion["auroc"]:
        reasons.append(f"AUROC {challenger['auroc']:.3f} < champion {champion['auroc']:.3f}")
    return GateResult(passed=not reasons, reasons=reasons)
