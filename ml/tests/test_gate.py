from rpm_ml.evaluation.gate import MIN_RECALL_CRITICAL, TARGET_RECALL_CRITICAL, evaluate_anomaly_gate, evaluate_risk_gate

PERSISTENCE = {"macro_f1": 0.55, "recall_critical": 0.31}
GOOD = {"macro_f1": 0.65, "recall_critical": 0.85}


def test_first_model_passes_when_above_absolute_thresholds_and_persistence():
    assert evaluate_risk_gate(GOOD, PERSISTENCE, champion=None).passed


def test_rejected_below_absolute_thresholds():
    result = evaluate_risk_gate({"macro_f1": 0.58, "recall_critical": 0.70}, PERSISTENCE)
    assert not result.passed
    assert len(result.reasons) == 2


def test_rejected_when_not_better_than_persistence():
    result = evaluate_risk_gate(GOOD, {"macro_f1": 0.65, "recall_critical": 0.9})
    assert not result.passed
    assert "persistence" in result.reasons[0]


def test_rejected_when_worse_than_champion_on_either_metric():
    champion = {"macro_f1": 0.66, "recall_critical": 0.80}
    result = evaluate_risk_gate(GOOD, PERSISTENCE, champion)
    assert not result.passed
    assert any("champion" in reason for reason in result.reasons)


def test_passes_when_equal_to_champion():
    assert evaluate_risk_gate(GOOD, PERSISTENCE, dict(GOOD)).passed


def test_recall_exactly_at_threshold_passes():
    assert evaluate_risk_gate({"macro_f1": 0.65, "recall_critical": MIN_RECALL_CRITICAL}, PERSISTENCE).passed


def test_tau_target_keeps_margin_above_gate_threshold():
    assert TARGET_RECALL_CRITICAL > MIN_RECALL_CRITICAL


ANOMALY_GOOD = {"auroc": 0.82, "precision": 0.5, "recall": 0.15, "f1": 0.23}


def test_anomaly_gate_first_model_passes_above_auroc_threshold():
    assert evaluate_anomaly_gate(ANOMALY_GOOD, champion=None).passed


def test_anomaly_gate_rejects_below_auroc_threshold():
    result = evaluate_anomaly_gate({"auroc": 0.70})
    assert not result.passed
    assert "AUROC" in result.reasons[0]


def test_anomaly_gate_rejects_lower_auroc_than_champion_but_accepts_equal():
    assert not evaluate_anomaly_gate(ANOMALY_GOOD, {"auroc": 0.85}).passed
    assert evaluate_anomaly_gate(ANOMALY_GOOD, dict(ANOMALY_GOOD)).passed
