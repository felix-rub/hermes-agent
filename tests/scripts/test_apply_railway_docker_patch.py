from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "apply_railway_docker_patch.py"
REPO_ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("apply_railway_docker_patch", SCRIPT)
assert spec is not None
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_apply_railway_patch_removes_volume_and_sets_dashboard_cmd(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        '\n'.join(
            [
                'FROM debian:13.4',
                'RUN mkdir -p /opt/data',
                'VOLUME [ "/opt/data" ]',
                'ENTRYPOINT [ "/init", "/opt/hermes/docker/main-wrapper.sh" ]',
                'CMD [ ]',
                '',
            ]
        ),
        encoding="utf-8",
    )

    assert module.apply_railway_patch(dockerfile) is True
    patched = dockerfile.read_text(encoding="utf-8")

    assert 'VOLUME [ "/opt/data" ]' not in patched
    assert 'CMD ["sh", "-c", "exec hermes dashboard --host 0.0.0.0 --port ${PORT:-9119} --no-open --insecure"]' in patched
    assert "Railway serves the dashboard from the container's main process" in patched


def test_apply_railway_patch_is_idempotent(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        '\n'.join(
            [
                'FROM debian:13.4',
                'RUN mkdir -p /opt/data',
                "# Railway serves the dashboard from the container's main process and injects",
                '# PORT at runtime. Use sh -c so ${PORT:-9119} is expanded after deployment.',
                'CMD ["sh", "-c", "exec hermes dashboard --host 0.0.0.0 --port ${PORT:-9119} --no-open --insecure"]',
                '',
            ]
        ),
        encoding="utf-8",
    )

    assert module.apply_railway_patch(dockerfile) is False


def test_apply_railway_patch_migrates_legacy_sleep_block(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        '\n'.join(
            [
                'FROM debian:13.4',
                'RUN mkdir -p /opt/data',
                '# Railway deploys the container as a long-running service; keep the main process',
                '# alive while s6-supervised services start and run in the background.',
                'CMD ["sleep", "infinity"]',
                '',
            ]
        ),
        encoding="utf-8",
    )

    assert module.apply_railway_patch(dockerfile) is True
    patched = dockerfile.read_text(encoding="utf-8")

    assert "sleep infinity" not in patched
    assert 'CMD ["sleep", "infinity"]' not in patched
    assert 'CMD ["sh", "-c", "exec hermes dashboard --host 0.0.0.0 --port ${PORT:-9119} --no-open --insecure"]' in patched


def test_repository_dockerfile_has_railway_dashboard_contract() -> None:
    dockerfile = REPO_ROOT / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")

    assert 'VOLUME [ "/opt/data" ]' not in text
    assert 'CMD ["sleep", "infinity"]' not in text
    assert 'CMD ["sh", "-c", "exec hermes dashboard --host 0.0.0.0 --port ${PORT:-9119} --no-open --insecure"]' in text


def test_railway_config_forces_dashboard_deploy_contract() -> None:
    config = tomllib.loads((REPO_ROOT / "railway.toml").read_text(encoding="utf-8"))

    assert config["build"]["builder"] == "DOCKERFILE"
    assert config["build"]["dockerfilePath"] == "Dockerfile"
    assert config["deploy"]["healthcheckPath"] == "/api/status"
    assert config["deploy"]["healthcheckTimeout"] >= 300
    assert config["deploy"]["restartPolicyType"] == "ON_FAILURE"

    start_command = config["deploy"]["startCommand"]
    assert "/init /opt/hermes/docker/main-wrapper.sh" in start_command
    assert "hermes dashboard" in start_command
    assert "--host 0.0.0.0" in start_command
    assert "--port ${PORT:-9119}" in start_command
    assert "--no-open --insecure" in start_command