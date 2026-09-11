from rpm_streaming.consumer.alerting import AlertHistory, alerts_to_create, effective_risk_threshold


def test_crossing_threshold_without_history_creates_alert():
    assert alerts_to_create({"RISK": True, "ANOMALY": False}, 10, {}, cooldown_hours=4) == ["RISK"]


def test_warning_or_nothing_triggered_creates_no_alert():
    assert alerts_to_create({"RISK": False, "ANOMALY": False}, 10, {}, cooldown_hours=4) == []


def test_open_alert_of_same_type_blocks_new_one():
    history = {"RISK": AlertHistory(has_open=True, last_hour_index=1)}
    assert alerts_to_create({"RISK": True}, 50, history, cooldown_hours=4) == []


def test_cooldown_in_data_hours_after_previous_alert_is_resolved():
    history = {"RISK": AlertHistory(has_open=False, last_hour_index=10)}
    assert alerts_to_create({"RISK": True}, 13, history, cooldown_hours=4) == []
    assert alerts_to_create({"RISK": True}, 14, history, cooldown_hours=4) == ["RISK"]


def test_risk_and_anomaly_together_create_two_alerts_independently():
    assert alerts_to_create({"RISK": True, "ANOMALY": True}, 5, {}, cooldown_hours=4) == ["RISK", "ANOMALY"]
    history = {"RISK": AlertHistory(has_open=True, last_hour_index=4)}
    assert alerts_to_create({"RISK": True, "ANOMALY": True}, 5, history, cooldown_hours=4) == ["ANOMALY"]


def test_admin_threshold_overrides_champion_tau_only_when_set():
    assert effective_risk_threshold(None, 0.22) == 0.22
    assert effective_risk_threshold(0.4, 0.22) == 0.4
