# Releasing `sync-core`

Nothing here publishes. Publishing is public and irreversible and is a decision a human makes;
this is the sequence that makes the artifacts correct first, and the checks that would have
caught the two defects a published wheel cannot be repaired for.

## Why a checklist and not only a test

`tests/test_core_distribution.py` builds the core wheel on every run and asserts what a
recipient receives: the Apache text, `License-File`, `Description-Content-Type`, and a
description that names the authoring guide and the conformance kit. That is the half worth
paying for on every `pytest`.

The rest costs a second wheel build. The runtime distribution is the large one, and a suite of
2658 tests should not build it to assert a packaging property that changes about once a
milestone — so `test_the_runtime_wheel_still_excludes_the_core_package` asserts the
configuration and the command below asserts the artifact. If those two ever disagree, the
artifact is right.

## The sequence

```console
uv run pytest tests/test_core_distribution.py
uv build --wheel --package sync-core -o dist
uv build --wheel --package sync -o dist
```

Then read the two wheels rather than trusting that they were built:

```console
uv run python -c "
import zipfile
core = zipfile.ZipFile('dist/sync_core-0.1.0-py3-none-any.whl')
runtime = zipfile.ZipFile('dist/sync-0.1.0-py3-none-any.whl')
metadata = core.read('sync_core-0.1.0.dist-info/METADATA').decode('utf-8')
print('licence in core wheel:',
      [n for n in core.namelist() if 'licenses/' in n and not n.endswith('/')])
print('License-File header  :', 'License-File: LICENSE' in metadata)
print('description body     :', len(metadata.split(chr(10)*2, 1)[1].strip()), 'characters')
print('core in runtime wheel:', [n for n in runtime.namelist() if n.startswith('sync/core')])
"
```

Expected: one licence path, `True`, a few thousand characters, and an empty list. An empty list
is the one that matters — the two distributions must never own the same files, because
uninstalling either would otherwise take `sync/core` out from under the other.

Last, install the core wheel alone and confirm it still arrives with five other packages and
nothing from the runtime. `test_the_core_distribution_installs_and_works_without_the_runtime`
does exactly this and is the cheaper way to run it.

## What is still open before a first upload

- **The two versions move together.** `pyproject.toml` pins `sync-core==0.1.0` exactly, so
  publishing a core release without the runtime that was built against it produces a pairing
  nobody tested. Whoever publishes decides whether they go up together or whether the pin
  becomes a range, and that is a release-policy decision rather than a packaging one.
- **A metadata defect cannot be fixed in place.** PyPI does not accept a re-upload of a file for
  an existing version, so anything wrong in `0.1.0` is repaired by burning a version number.
  Read the artifacts before uploading, not after.
- **Nothing has been uploaded to TestPyPI either.** The rendering of the description on a real
  index has not been seen, only that a description exists and declares its content type.
