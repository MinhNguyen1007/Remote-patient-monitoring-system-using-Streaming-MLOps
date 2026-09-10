"""Quality gate Champion–Challenger — docs/design/02_9 mục 2.9.5 và 02_10 mục 2.10.3."""

from dataclasses import dataclass, field

MIN_MACRO_F1 = 0.60
MIN_RECALL_CRITICAL = 0.80


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
