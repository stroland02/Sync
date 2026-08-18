"""`copy_into_container` and `copy_out_of_container` (B97 Decision 1): the host-to-sandbox and
sandbox-to-host halves the now-deleted `copy_between_containers` never covered, because neither
of its endpoints was ever the host.

Own file rather than added to `test_patch_sandbox.py`: Lane C owns that file for B183.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sync.remediate import sandbox

_TEST_IMAGE = "python:3.12-slim"


@pytest.mark.docker
def test_copy_into_container_places_a_host_file_at_the_named_path():
    with tempfile.TemporaryDirectory() as host_dir:
        host_file = Path(host_dir) / "payload.txt"
        host_file.write_text("from the host", encoding="utf-8")

        with sandbox.ephemeral_container(image=_TEST_IMAGE) as container:
            sandbox.copy_into_container(container, str(host_file), "/workspace/payload.txt")
            result = sandbox._docker("exec", container.id, "cat", "/workspace/payload.txt")
            assert result.stdout == "from the host"


@pytest.mark.docker
def test_copy_into_container_creates_missing_parent_directories():
    with tempfile.TemporaryDirectory() as host_dir:
        host_file = Path(host_dir) / "payload.txt"
        host_file.write_text("nested", encoding="utf-8")

        with sandbox.ephemeral_container(image=_TEST_IMAGE) as container:
            sandbox.copy_into_container(container, str(host_file), "/workspace/deep/nested/payload.txt")
            result = sandbox._docker("exec", container.id, "cat", "/workspace/deep/nested/payload.txt")
            assert result.stdout == "nested"


@pytest.mark.docker
def test_copy_out_of_container_brings_a_container_file_back_to_the_host():
    with tempfile.TemporaryDirectory() as host_dir:
        with sandbox.ephemeral_container(image=_TEST_IMAGE) as container:
            write = sandbox._docker(
                "exec", container.id, "sh", "-c", "mkdir -p /workspace && echo 'from the container' > /workspace/out.txt"
            )
            assert write.returncode == 0, write.stderr

            host_path = str(Path(host_dir) / "out.txt")
            sandbox.copy_out_of_container(container, "/workspace/out.txt", host_path)

            assert Path(host_path).read_text(encoding="utf-8").strip() == "from the container"


@pytest.mark.docker
def test_copy_out_of_container_of_a_path_that_never_existed_raises():
    with sandbox.ephemeral_container(image=_TEST_IMAGE) as container:
        with pytest.raises(RuntimeError, match="docker cp out of"):
            sandbox.copy_out_of_container(container, "/workspace/never-written.txt", "/tmp/wherever.txt")
