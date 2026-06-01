from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "apply_railway_docker_patch.py"
spec = importlib.util.spec_from_file_location("apply_railway_docker_patch", SCRIPT)
assert spec is not None
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_apply_railway_patch_removes_volume_and_sets_keepalive_cmd(tmp_path: Path) -> None:
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
    assert 'CMD ["sleep", "infinity"]' in patched
    assert "Railway deploys the container as a long-running service" in patched


def test_apply_railway_patch_is_idempotent(tmp_path: Path) -> None:
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

    assert module.apply_railway_patch(dockerfile) is False