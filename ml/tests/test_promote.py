import numpy as np
import pytest

mlflow = pytest.importorskip("mlflow")
from mlflow import MlflowClient  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

from rpm_ml.pipelines.promote import file_hashes, promote_model  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_global_uris():
    tracking, registry = mlflow.get_tracking_uri(), mlflow.get_registry_uri()
    yield
    mlflow.set_tracking_uri(tracking)
    mlflow.set_registry_uri(registry)


def _registry(tmp_path, name):
    uri = f"sqlite:///{(tmp_path / f'{name}.db').as_posix()}"
    client = MlflowClient(tracking_uri=uri, registry_uri=uri)
    client.create_experiment("rpm", artifact_location=(tmp_path / f"{name}_artifacts").as_uri())
    return uri, client


def _train_source(uri):
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    mlflow.set_experiment("rpm")
    x = np.array([[0.0], [1.0], [2.0], [3.0]])
    model = LogisticRegression().fit(x, [0, 0, 1, 1])
    with mlflow.start_run() as run:
        mlflow.log_params({"model_family": "logistic_regression"})
        mlflow.log_metrics({"test_macro_f1": 0.623})
        mlflow.set_tags({"gate": "passed"})
        mlflow.log_dict({"heart_rate": [1, 2, 3]}, "reference_stats.json")
        mlflow.log_dict({"thresholds": {"heart_rate": 0.3}}, "drift_thresholds.json")
        info = mlflow.sklearn.log_model(model, name="model", registered_model_name="risk_classifier")
    client = MlflowClient(tracking_uri=uri, registry_uri=uri)
    client.set_model_version_tag("risk_classifier", info.registered_model_version, "tau_critical", "0.22")
    client.set_registered_model_alias("risk_classifier", "champion", info.registered_model_version)
    return run.info.run_id, model, x


def test_promote_copies_identical_artifact_and_run_context(tmp_path):
    source_uri, _ = _registry(tmp_path, "source")
    target_uri, target = _registry(tmp_path, "target")
    source_run, model, x = _train_source(source_uri)
    # promote không được dựa vào URI toàn cục: trỏ nó sang một registry thứ ba (rỗng)
    mlflow.set_tracking_uri(f"sqlite:///{(tmp_path / 'unrelated.db').as_posix()}")
    mlflow.set_registry_uri(f"sqlite:///{(tmp_path / 'unrelated.db').as_posix()}")

    result = promote_model(source_uri, target_uri, "risk_classifier")

    assert result["status"] == "promoted"
    version = target.get_model_version_by_alias("risk_classifier", "champion")
    assert target.get_model_version_by_alias("risk_classifier", "challenger").version == version.version
    assert version.tags["tau_critical"] == "0.22"
    assert version.tags["promoted_from_run_id"] == source_run
    run = target.get_run(version.run_id)
    assert run.data.metrics["test_macro_f1"] == 0.623
    assert run.data.params["model_family"] == "logistic_regression"
    assert run.data.tags["gate"] == "passed"
    mlflow.set_tracking_uri(target_uri)
    mlflow.set_registry_uri(target_uri)
    # drift_check đọc 2 file này từ run của champion
    thresholds = mlflow.artifacts.load_dict(f"runs:/{version.run_id}/drift_thresholds.json")
    assert thresholds == {"thresholds": {"heart_rate": 0.3}}
    promoted = mlflow.sklearn.load_model("models:/risk_classifier@champion")
    assert np.array_equal(promoted.predict_proba(x), model.predict_proba(x))


def test_promote_twice_is_a_no_op(tmp_path):
    source_uri, _ = _registry(tmp_path, "source")
    target_uri, target = _registry(tmp_path, "target")
    _train_source(source_uri)
    first = promote_model(source_uri, target_uri, "risk_classifier")
    second = promote_model(source_uri, target_uri, "risk_classifier")
    assert second == {"model": "risk_classifier", "status": "unchanged", "source_version": "1",
                      "target_version": first["target_version"]}
    assert len(target.search_model_versions("name='risk_classifier'")) == 1


def test_file_hashes_use_posix_relative_paths(tmp_path):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "a.bin").write_bytes(b"x")
    assert list(file_hashes(tmp_path)) == ["artifacts/a.bin"]
