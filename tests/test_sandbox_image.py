"""B97 Decision 2: an idempotent build/tag/pre-warm mechanism for the patch-sandbox
image, kept off a real remediation run's critical path.

`docker/patch-sandbox/Dockerfile` existed before this file did -- built and probed by
hand once, per its own comment -- but nothing in this tree computed a reproducible tag
for it, checked whether that tag already existed, or built it when it didn't. The
latency spec (`docs/superpowers/specs/2026-07-25-sync-latency-architecture.md`, Lever
2) is explicit that this has to be precomputation: a real patch attempt must never pay
for `docker build`. `sync.remediate.sandbox_image` is that precomputation.

- `test_compute_image_tag_*` prove the tag is a pure function of the Dockerfile's
  bytes and the build args -- no Docker daemon involved, so these run outside the
  `docker` marker and stay fast on every run.
- `test_ensure_image_built_builds_on_miss_then_is_a_no_op_on_repeat_call` is the
  mechanism proof this repository's culture asks for: a real Docker Desktop instance,
  not a mocked `docker` call, with a positive control (the image actually exists after
  the first call) and a negative one (the image's own ID -- Docker's content identity,
  not this module's -- is unchanged after the second call, which is stronger evidence
  of "no rebuild happened" than timing the call would be).
- `test_ensure_image_built_builds_the_real_patch_sandbox_image` runs the same
  mechanism against the actual shipped Dockerfile rather than a synthetic stand-in,
  proving Decision 2 closes for the artifact this backlog entry is actually about.

Requires a working Docker Desktop with Linux containers, the same local dependency
`tests/test_patch_sandbox.py` already has.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# The digest `docker/patch-sandbox/Dockerfile` pins its base image to. Reused here so
# a synthetic test Dockerfile builds against an image this host already has pulled,
# rather than each test paying its own pull.
_BASE_DIGEST = "python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134"


def _write_dockerfile(tmp_path: Path, instruction: str) -> Path:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(f"FROM {_BASE_DIGEST}\n{instruction}\n", encoding="utf-8")
    return dockerfile


def test_compute_image_tag_changes_when_dockerfile_content_changes(tmp_path):
    from sync.remediate import sandbox_image

    dockerfile = _write_dockerfile(tmp_path, "RUN echo a")
    tag_a = sandbox_image.compute_image_tag(dockerfile, sandbox_image.DEFAULT_BUILD_ARGS)

    dockerfile = _write_dockerfile(tmp_path, "RUN echo b")
    tag_b = sandbox_image.compute_image_tag(dockerfile, sandbox_image.DEFAULT_BUILD_ARGS)

    assert tag_a != tag_b


def test_compute_image_tag_changes_when_build_args_change(tmp_path):
    from sync.remediate import sandbox_image

    dockerfile = _write_dockerfile(tmp_path, "RUN echo a")
    tag_node_22 = sandbox_image.compute_image_tag(dockerfile, {"NODE_MAJOR": "22"})
    tag_node_23 = sandbox_image.compute_image_tag(dockerfile, {"NODE_MAJOR": "23"})

    assert tag_node_22 != tag_node_23


def test_compute_image_tag_is_stable_for_identical_input(tmp_path):
    from sync.remediate import sandbox_image

    dockerfile = _write_dockerfile(tmp_path, "RUN echo a")
    first = sandbox_image.compute_image_tag(dockerfile, sandbox_image.DEFAULT_BUILD_ARGS)
    second = sandbox_image.compute_image_tag(dockerfile, sandbox_image.DEFAULT_BUILD_ARGS)

    assert first == second


def _image_id(tag: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", tag, "--format", "{{.Id}}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.docker
def test_ensure_image_built_builds_on_miss_then_is_a_no_op_on_repeat_call(tmp_path):
    from sync.remediate import sandbox_image

    dockerfile = _write_dockerfile(tmp_path, "RUN echo prewarm-test")
    build_args = {"FLAVOR": "prewarm-test"}
    tag = None
    try:
        tag = sandbox_image.ensure_image_built(dockerfile, build_args)
        first_id = _image_id(tag)
        assert first_id, "image was not actually built"

        tag_again = sandbox_image.ensure_image_built(dockerfile, build_args)
        second_id = _image_id(tag_again)

        assert tag_again == tag
        assert second_id == first_id, (
            "the image's own ID changed on the second call, meaning a rebuild "
            "happened instead of the expected inspect-and-skip"
        )
    finally:
        if tag is not None:
            subprocess.run(
                ["docker", "rmi", "-f", tag],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )


@pytest.mark.docker
def test_ensure_image_built_rebuilds_a_tag_that_never_existed(tmp_path):
    """A miss triggers a real build, proven against a tag that has certainly never
    been built before (fresh, uniquely-worded instruction) -- not inferred from the
    absence of an exception.
    """
    from sync.remediate import sandbox_image

    dockerfile = _write_dockerfile(tmp_path, "RUN echo this-content-has-never-been-built-before")
    build_args = {"FLAVOR": "never-built-before"}
    # `ensure_image_built` hashes `build_args` merged on top of `DEFAULT_BUILD_ARGS`,
    # not `build_args` alone -- the expected tag has to be computed the same way, or
    # this assertion would be checking this test's own arithmetic against the
    # module's rather than the module's tag against the module's build.
    tag = sandbox_image.compute_image_tag(dockerfile, {**sandbox_image.DEFAULT_BUILD_ARGS, **build_args})
    try:
        preexisting = subprocess.run(
            ["docker", "image", "inspect", tag],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        assert preexisting.returncode != 0, "positive control failed: this tag already existed"

        returned_tag = sandbox_image.ensure_image_built(dockerfile, build_args)
        assert returned_tag == tag
        assert _image_id(tag)
    finally:
        subprocess.run(
            ["docker", "rmi", "-f", tag],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )


@pytest.mark.docker
def test_ensure_image_built_builds_the_real_patch_sandbox_image():
    """Decision 2 end to end: the actual `docker/patch-sandbox/Dockerfile` this
    repository ships, built and tagged through the same mechanism a worker startup
    or a scheduled pre-warm would call -- not a synthetic stand-in. Slower than the
    tests above, because apt, Node, and npm all resolve for real: that cost is
    exactly what this decision keeps off a real patch attempt's critical path, and
    this test pays it once rather than asserting it away.

    Deliberately does not `docker rmi` afterward -- the image this leaves behind is
    the real pre-warmed artifact a subsequent local run should be able to reuse for
    free, which is the whole point of pre-warming.
    """
    from sync.remediate import sandbox_image

    tag = sandbox_image.ensure_image_built()
    inspect = subprocess.run(
        ["docker", "image", "inspect", tag],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert inspect.returncode == 0, f"ensure_image_built returned a tag that does not exist: {inspect.stderr}"

    second_tag = sandbox_image.ensure_image_built()
    assert second_tag == tag
