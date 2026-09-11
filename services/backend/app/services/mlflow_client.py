"""Đọc τ_critical khuyến nghị (tag của risk_classifier@champion) qua MLflow REST — backend không cần thư viện mlflow."""

import logging

import httpx

log = logging.getLogger(__name__)


def champion_tau_critical(tracking_uri: str, model_name: str = "risk_classifier", timeout: float = 3.0) -> float | None:
    try:
        response = httpx.get(
            f"{tracking_uri.rstrip('/')}/api/2.0/mlflow/registered-models/alias",
            params={"name": model_name, "alias": "champion"},
            timeout=timeout,
        )
        response.raise_for_status()
        tags = {t["key"]: t["value"] for t in response.json()["model_version"].get("tags", [])}
        return float(tags["tau_critical"])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("không đọc được tau_critical của champion: %s", exc)
        return None
