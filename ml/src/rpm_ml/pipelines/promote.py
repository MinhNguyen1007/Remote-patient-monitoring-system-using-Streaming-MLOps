"""Chuyển (promote) đúng artifact model champion từ registry MLflow này sang registry MLflow khác — không huấn luyện lại.

Nguyên tắc "build once, deploy many": model được đánh giá và qua quality gate ở môi trường phát triển chính là model
chạy ở production. Huấn luyện lại ở máy khác không bảo đảm ra cùng model — GroupKFold (sklearn 1.3.2) sắp nhóm bằng
np.argsort không ổn định, thứ tự các nhóm cùng kích thước đổi theo tập lệnh SIMD của CPU, nên fold, τ_critical và metric
lệch nhau (ghi nhận 2026-09-30: τ 0,22 trên máy phát triển, 0,23 trên EC2 Sapphire Rapids).

Với mỗi model:
  1. lấy version mang alias nguồn (mặc định champion) và run của nó;
  2. tải thư mục model + toàn bộ artifact của run (reference_stats.json, drift_thresholds.json dùng cho drift_check);
  3. tạo run ở registry đích, cùng experiment, cùng params / metric / tag, thêm tag truy vết nguồn;
  4. đăng ký version mới từ artifact vừa log, chép tag của version;
  5. tải lại model từ đích, so hash từng file với nguồn — chỉ gán alias champion (và challenger) khi trùng khít.
Đã có champion ở đích mang cùng `promoted_from_run_id` → bỏ qua (chạy lại an toàn).

  python -m rpm_ml.pipelines.promote --source http://localhost:5000 --target http://localhost:15000
"""

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from mlflow.entities import Metric, Param, RunTag
from mlflow.exceptions import MlflowException

MODELS = ("risk_classifier", "anomaly_detector")
MODEL_ARTIFACT_PATH = "model"
SOURCE_TAGS = ("promoted_from_uri", "promoted_from_run_id", "promoted_from_version")


def file_hashes(root: Path) -> dict[str, str]:
    """SHA-256 của mọi file dưới `root`, khoá là đường dẫn tương đối dạng POSIX."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _champion(client: MlflowClient, name: str, alias: str):
    try:
        return client.get_model_version_by_alias(name, alias)
    except MlflowException:
        return None


def promote_model(source_uri: str, target_uri: str, name: str, alias: str = "champion") -> dict:
    # registry_uri tường minh: MlflowClient(uri) vẫn dùng registry URI toàn cục nếu đã được đặt
    source = MlflowClient(tracking_uri=source_uri, registry_uri=source_uri)
    target = MlflowClient(tracking_uri=target_uri, registry_uri=target_uri)
    version = source.get_model_version_by_alias(name, alias)
    source_version = str(version.version)  # MLflow 3 trả int, tag phải là chuỗi
    run = source.get_run(version.run_id)

    existing = _champion(target, name, "champion")
    if existing is not None and existing.tags.get("promoted_from_run_id") == run.info.run_id:
        return {"model": name, "status": "unchanged", "source_version": source_version,
                "target_version": str(existing.version)}

    with tempfile.TemporaryDirectory() as tmp:
        # Không dùng URI "models:/…": MLflow tra registry theo URI toàn cục, không theo tracking_uri truyền vào
        model_dir = Path(mlflow.artifacts.download_artifacts(
            artifact_uri=source.get_model_version_download_uri(name, source_version),
            dst_path=f"{tmp}/model", tracking_uri=source_uri))
        run_dir = Path(tmp) / "run"
        run_dir.mkdir()
        if source.list_artifacts(run.info.run_id):
            mlflow.artifacts.download_artifacts(run_id=run.info.run_id, dst_path=str(run_dir), tracking_uri=source_uri)

        experiment = source.get_experiment(run.info.experiment_id).name
        target_experiment = target.get_experiment_by_name(experiment)
        experiment_id = (target_experiment.experiment_id if target_experiment is not None
                         else target.create_experiment(experiment))
        provenance = {"promoted_from_uri": source_uri, "promoted_from_run_id": run.info.run_id,
                      "promoted_from_version": source_version}
        run_tags = {k: v for k, v in run.data.tags.items() if not k.startswith("mlflow.")} | provenance
        new_run = target.create_run(experiment_id, run_name=f"promote_{name}_v{source_version}",
                                    tags={"mlflow.runName": f"promote_{name}_v{source_version}"})
        run_id = new_run.info.run_id
        now = int(time.time() * 1000)
        target.log_batch(
            run_id,
            metrics=[Metric(key, value, now, 0) for key, value in run.data.metrics.items()],
            params=[Param(key, value) for key, value in run.data.params.items()],
            tags=[RunTag(key, value) for key, value in run_tags.items()],
        )
        if any(run_dir.iterdir()):
            target.log_artifacts(run_id, str(run_dir))
        target.log_artifacts(run_id, str(model_dir), MODEL_ARTIFACT_PATH)
        target.set_terminated(run_id)

        try:
            target.get_registered_model(name)
        except MlflowException:
            target.create_registered_model(name)
        model_source = f"{target.get_run(run_id).info.artifact_uri}/{MODEL_ARTIFACT_PATH}"
        new_version = str(target.create_model_version(name, model_source, run_id=run_id).version)
        for key, value in (version.tags | provenance).items():
            target.set_model_version_tag(name, new_version, key, value)

        check_dir = Path(mlflow.artifacts.download_artifacts(
            artifact_uri=target.get_model_version_download_uri(name, new_version),
            dst_path=f"{tmp}/check", tracking_uri=target_uri))
        hashes = file_hashes(model_dir)
        result = {"model": name, "source_version": source_version, "target_version": new_version,
                  "run_id": run_id, "files": len(hashes)}
        if file_hashes(check_dir) != hashes:
            target.set_model_version_tag(name, new_version, "gate", "rejected")
            target.set_model_version_tag(name, new_version, "gate_reasons", "artifact khác nguồn sau khi chuyển")
            return result | {"status": "mismatch"}
        target.set_registered_model_alias(name, "challenger", new_version)
        target.set_registered_model_alias(name, "champion", new_version)
    return result | {"status": "promoted"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="tracking URI registry nguồn")
    parser.add_argument("--target", required=True, help="tracking URI registry đích")
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--alias", default="champion", help="alias của version nguồn cần chuyển")
    args = parser.parse_args()
    results = [promote_model(args.source, args.target, name, args.alias) for name in args.models]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if any(result["status"] == "mismatch" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
