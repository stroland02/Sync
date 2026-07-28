import subprocess
from pathlib import Path

import pytest

from sync.core import Patch, RepoRef, VerifyResult
from sync.index.tsc import run_tsc
from sync.index.typescript import TypeScriptAdapter


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions": {"strict": true, "noEmit": true, "target": "ES2022", "module": "ESNext",'
        ' "moduleResolution": "bundler", "skipLibCheck": true}, "include": ["src"]}',
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    return tmp_path


def test_clean_project_verifies_ok(project: Path):
    (project / "src" / "a.ts").write_text("export const n: number = 1;\n", encoding="utf-8")
    result = run_tsc(project)
    assert result.ok is True
    assert result.diagnostics == ""


def test_type_error_fails_and_diagnostics_are_captured(project: Path):
    (project / "src" / "a.ts").write_text("export const n: number = 'not a number';\n", encoding="utf-8")
    result = run_tsc(project)
    assert result.ok is False
    assert "TS2322" in result.diagnostics


def test_reading_a_property_that_does_not_exist_fails(project: Path):
    (project / "src" / "a.ts").write_text(
        "type Charge = { id: string };\n"
        "declare const c: Charge;\n"
        "export const s = c.status;\n",
        encoding="utf-8",
    )
    result = run_tsc(project)
    assert result.ok is False
    assert "TS2339" in result.diagnostics


def test_timeout_is_caught_and_reported_as_a_failed_verification(project: Path):
    """A hung compiler must come back as a failed verification, not an exception.

    Task 9's graph routes entirely on `VerifyResult.ok`: it feeds `diagnostics`
    into the next patch attempt and abandons the finding after three. None of
    that machinery handles an exception escaping the node, so a timeout has to
    be absorbed as one failed attempt, not left to crash the graph.

    `timeout` is forced absurdly low (1 millisecond) rather than mocked, so
    this exercises a real `subprocess.TimeoutExpired` from a real `tsc`
    invocation: spawning node and resolving npx alone takes far longer than
    that on any machine, so the process is reliably still running when the
    timeout fires.
    """
    (project / "src" / "a.ts").write_text("export const n: number = 1;\n", encoding="utf-8")
    result = run_tsc(project, timeout=0.001)
    assert result.ok is False
    assert "timed out" in result.diagnostics


def test_non_ascii_identifier_does_not_crash_the_gate(project: Path):
    """A non-ASCII identifier anywhere in the project must not crash run_tsc.

    tsc emits UTF-8 diagnostics. Decoding subprocess output with the locale
    encoding (cp1252 on this machine) instead of UTF-8 raises UnicodeDecodeError
    on a byte like the second one in 'Á'.encode('utf-8'), which is undefined
    in cp1252 -- this must not turn a real type error into a crashed gate.
    """
    (project / "src" / "a.ts").write_text(
        "type Álias = { id: string };\n"
        "declare const c: Álias;\n"
        "export const s = c.status;\n",
        encoding="utf-8",
    )
    result = run_tsc(project)
    assert result.ok is False
    assert "TS2339" in result.diagnostics


def test_static_verify_installs_dependencies_before_typechecking(tmp_path, monkeypatch, git):
    from sync.index import typescript

    # A real repository, because `static_verify` now asks git what a push would
    # carry before it compiles anything. A bare directory is not a case the
    # pipeline can reach -- every clone it verifies came from `git clone`.
    git(["init", "-q"], tmp_path)

    order: list[str] = []
    monkeypatch.setattr(
        "sync.index.deps.install_dependencies", lambda path, **kw: order.append("install")
    )
    monkeypatch.setattr(
        "sync.index.tsc.run_tsc",
        lambda path, **kw: (order.append("tsc"), VerifyResult(ok=True))[1],
    )

    repo = RepoRef(repo_id="r", url="u", local_path=str(tmp_path), head_sha="0" * 40)
    adapter = typescript.TypeScriptAdapter(vendor_adapter=None)
    adapter.prepare(repo)

    order.clear()
    adapter.static_verify(repo, Patch(diff="d", strategy="agent", rationale="r"))

    assert order == ["install", "tsc"]


def _verify(repo_path: Path, git) -> VerifyResult:
    """Verify the way the graph does: `prepare` measures the tree before the
    patch, then `static_verify` measures the tree with it.

    The fixtures below hand over a clone the patch is already applied to, so the
    tracked modifications are set aside for the measurement and written back
    before the verification -- which is the ordering the graph gets for free by
    running `prepare` in a node of its own.
    """
    repo = RepoRef(repo_id="r", url="u", local_path=str(repo_path), head_sha="0" * 40)
    adapter = TypeScriptAdapter(vendor_adapter=None)

    changed = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo_path,
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.split()
    patched = {name: (repo_path / name).read_text(encoding="utf-8") for name in changed}
    git(["checkout", "--", "."], repo_path)
    adapter.prepare(repo)
    for name, text in patched.items():
        (repo_path / name).write_text(text, encoding="utf-8")

    return adapter.static_verify(repo, Patch(diff="d", strategy="agent", rationale="r"))


def test_static_verify_rejects_a_patch_that_only_typechecks_with_untracked_files(patched_clone: Path, git):
    """The gate must describe the artifact that ships, not the tree the agent left.

    The working tree here typechecks clean. The branch `push_branch` would
    create does not, because the declaration `src/a.ts` depends on lives in an
    untracked, gitignored file. A green verdict here is the M0 acceptance
    failure: the fast gate approving code the customer's CI then rejected.
    """
    result = _verify(patched_clone, git)

    assert result.ok is False
    assert "TS2304" in result.diagnostics


def test_static_verify_leaves_the_agents_working_tree_as_it_found_it(patched_clone: Path, git):
    """The next patch attempt runs in this clone and has to see its own work.

    Reducing the tree to what ships is a measurement, not an edit: everything
    moved aside for the typecheck comes back, including the file that caused
    the rejection.
    """
    _verify(patched_clone, git)

    assert (patched_clone / "generated.d.ts").read_text(encoding="utf-8").startswith("declare type Generated")
    assert "Generated" in (patched_clone / "src" / "a.ts").read_text(encoding="utf-8")


def test_static_verify_passes_when_the_tracked_modifications_stand_on_their_own(patched_clone: Path, git):
    """The gate must not have become a gate on untracked files existing at all.

    Same clone, same gitignored file present -- but the patch no longer needs
    what it declares, so the branch typechecks and this must stay green.
    """
    (patched_clone / "src" / "a.ts").write_text("export const n: number = 2;\n", encoding="utf-8")

    assert _verify(patched_clone, git).ok is True


def test_prepare_installs_dependencies(tmp_path, monkeypatch, git):
    from sync.index import typescript

    # `prepare` measures the baseline once the install is done, so the tree has
    # to be a repository and the compiler has to answer.
    git(["init", "-q"], tmp_path)
    monkeypatch.setattr("sync.index.tsc.run_tsc", lambda path, **kw: VerifyResult(ok=True))

    calls: list[str] = []
    monkeypatch.setattr(
        "sync.index.deps.install_dependencies", lambda path, **kw: calls.append(str(path))
    )

    repo = RepoRef(repo_id="r", url="u", local_path=str(tmp_path), head_sha="0" * 40)
    adapter = typescript.TypeScriptAdapter(vendor_adapter=None)
    adapter.prepare(repo)

    assert calls == [str(Path(tmp_path).resolve())]


def test_static_verify_survives_the_build_artifact_the_typecheck_itself_writes(tmp_path, git):
    """The M0 acceptance run's abandonment, through the real compiler.

    `incremental` makes `tsc --noEmit` write `tsconfig.tsbuildinfo`, and
    `.gitignore` keeps it out of the repository -- so the gate holds it aside,
    the compiler writes a new one at that path while it is away, and the
    restore has to put the clone back anyway. The run abandoned the finding
    here, on a `FileExistsError` that says nothing about whether the patch was
    correct.
    """
    repo = tmp_path / "clone"
    (repo / "src").mkdir(parents=True)
    (repo / ".gitignore").write_text("tsconfig.tsbuildinfo\nnode_modules\n", encoding="utf-8")
    (repo / "tsconfig.json").write_text(
        '{"compilerOptions": {"strict": true, "noEmit": true, "incremental": true,'
        ' "target": "ES2022", "module": "ESNext", "moduleResolution": "bundler",'
        ' "skipLibCheck": true}, "include": ["src"]}',
        encoding="utf-8",
    )
    (repo / "src" / "a.ts").write_text("export const n: number = 1;\n", encoding="utf-8")

    git(["init", "-q", "-b", "main"], repo)
    git(["add", "."], repo)
    git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], repo)

    (repo / "tsconfig.tsbuildinfo").write_text("from an earlier build\n", encoding="utf-8")

    result = _verify(repo, git)

    assert result.ok is True
    assert (repo / "tsconfig.tsbuildinfo").read_text(encoding="utf-8") == "from an earlier build\n"


NEXT_ENV_IMPORTS = 15


@pytest.fixture()
def ambient_clone(tmp_path: Path, git) -> Path:
    """A committed project that does not typecheck on its own, in the shape the
    M0 acceptance run met.

    Next.js writes `next-env.d.ts` during a build, `tsconfig.json` lists it in
    `include`, and `.gitignore` keeps it out of the repository -- so the
    declarations that make `import logo from '@/public/logo.png'` resolve are in
    no checkout of the branch. `shipped_tree` holds the generated file out of
    the tree because it genuinely is not part of what `git add -u` commits, and
    the compiler then reports one unresolved module per image import: fifteen in
    the acceptance run, every one of them in the base tree, none of them fixable
    by any patch.
    """
    repo = tmp_path / "clone"
    (repo / "src").mkdir(parents=True)
    (repo / ".gitignore").write_text("ambient.d.ts\nnode_modules\n", encoding="utf-8")
    (repo / "tsconfig.json").write_text(
        '{"compilerOptions": {"strict": true, "noEmit": true, "target": "ES2022",'
        ' "module": "ESNext", "moduleResolution": "bundler", "skipLibCheck": true},'
        ' "include": ["src", "ambient.d.ts"]}',
        encoding="utf-8",
    )
    for index in range(NEXT_ENV_IMPORTS):
        (repo / "src" / f"asset{index}.ts").write_text(
            f'import logo from "@/public/logo{index}.png";\n'
            f"export const logo{index} = logo;\n",
            encoding="utf-8",
        )
    (repo / "src" / "billing.ts").write_text("export const amount: number = 100;\n", encoding="utf-8")

    git(["init", "-q", "-b", "main"], repo)
    git(["add", "."], repo)
    git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], repo)

    # Generated during a build, gitignored, and therefore present in the tree the
    # agent works in and absent from the tree that ships.
    (repo / "ambient.d.ts").write_text(
        'declare module "*.png" {\n  const src: string;\n  export default src;\n}\n',
        encoding="utf-8",
    )
    return repo


def _adapter_for(repo_path: Path) -> tuple[TypeScriptAdapter, RepoRef]:
    return (
        TypeScriptAdapter(vendor_adapter=None),
        RepoRef(repo_id="r", url="u", local_path=str(repo_path), head_sha="0" * 40),
    )


def _shipped_diagnostics(repo_path: Path) -> list:
    from sync.index.deps import DEPENDENCY_DIRS
    from sync.index.shipped_tree import shipped_tree
    from sync.index.tsc import parse_diagnostics

    with shipped_tree(repo_path, keep=DEPENDENCY_DIRS):
        return parse_diagnostics(run_tsc(repo_path).diagnostics)


def test_the_fixture_really_is_broken_before_any_patch(ambient_clone: Path):
    """Guards every test below it. If the shipped tree typechecked clean, they
    would all pass without the subtraction they exist to exercise."""
    assert len(_shipped_diagnostics(ambient_clone)) == NEXT_ENV_IMPORTS


def test_errors_the_patch_did_not_cause_do_not_fail_the_gate(ambient_clone: Path):
    """The M0 acceptance run's abandonment.

    Fifteen unresolved modules, all of them in the base tree, and a patch that
    adds none. The customer's own CI generates the missing declarations before
    it typechecks, so a gate that rejects this is stricter than the gate it
    exists to approximate -- and each rejection costs up to three agent runs.
    """
    adapter, repo = _adapter_for(ambient_clone)
    adapter.prepare(repo)

    (ambient_clone / "src" / "billing.ts").write_text(
        "export const amount: number = 250;\n", encoding="utf-8"
    )
    result = adapter.static_verify(repo, Patch(diff="d", strategy="agent", rationale="r"))

    assert result.ok is True
    assert result.diagnostics == ""


def test_an_error_the_patch_introduced_still_fails_the_gate(ambient_clone: Path):
    """Subtraction must not become a way for a broken patch to hide among the
    noise, and what the next attempt is told must name only what it can fix."""
    adapter, repo = _adapter_for(ambient_clone)
    adapter.prepare(repo)

    (ambient_clone / "src" / "billing.ts").write_text(
        "export const amount: number = 'free';\n", encoding="utf-8"
    )
    result = adapter.static_verify(repo, Patch(diff="d", strategy="agent", rationale="r"))

    assert result.ok is False
    assert "TS2322" in result.diagnostics
    assert "TS2307" not in result.diagnostics
    assert len(result.diagnostics.splitlines()) == 1


def test_static_verify_refuses_to_run_without_a_baseline(ambient_clone: Path):
    """A gate that cannot say what was already broken cannot say what the patch
    broke. Passing would approve a patch on no evidence; quietly reverting to
    rejecting everything would abandon every finding on a repository that does
    not typecheck clean, which is the whole population this exists for."""
    adapter, repo = _adapter_for(ambient_clone)

    with pytest.raises(RuntimeError, match="baseline"):
        adapter.static_verify(repo, Patch(diff="d", strategy="agent", rationale="r"))


def test_prepare_refuses_when_the_baseline_cannot_be_computed(ambient_clone: Path, monkeypatch):
    """A timeout, a crashed compiler and a failed npx download all arrive as a
    non-zero exit carrying prose and no diagnostics. Reading that as an empty
    baseline would make every pre-existing error look introduced; reading it as
    a clean one would make every introduced error look pre-existing."""
    adapter, repo = _adapter_for(ambient_clone)
    monkeypatch.setattr(
        "sync.index.tsc.run_tsc",
        lambda path, **kw: VerifyResult(ok=False, diagnostics="typecheck timed out after 300s"),
    )

    with pytest.raises(RuntimeError, match="baseline"):
        adapter.prepare(repo)


def test_a_typecheck_that_could_not_run_fails_rather_than_passing(ambient_clone: Path, monkeypatch):
    """Same reasoning on the other side of the comparison: an uninterpretable
    run subtracts to nothing, and nothing must not read as approval."""
    adapter, repo = _adapter_for(ambient_clone)
    adapter.prepare(repo)

    monkeypatch.setattr(
        "sync.index.tsc.run_tsc",
        lambda path, **kw: VerifyResult(ok=False, diagnostics="typecheck timed out after 300s"),
    )
    result = adapter.static_verify(repo, Patch(diff="d", strategy="agent", rationale="r"))

    assert result.ok is False
    assert "timed out" in result.diagnostics


def test_the_baseline_is_measured_once_for_the_clone_that_serves_every_finding(
    ambient_clone: Path, monkeypatch
):
    """One clone serves every finding and `_reset_clone` returns it to the
    commit it was cloned at, so the tree `prepare` measures is the same tree
    each time. Paying for a second full `tsc` per finding buys nothing the
    latency specification would accept.
    """
    from sync.index import tsc as tsc_module

    real_run_tsc = tsc_module.run_tsc
    runs: list[Path] = []
    monkeypatch.setattr(
        "sync.index.tsc.run_tsc",
        lambda path, **kw: (runs.append(Path(path)), real_run_tsc(path, **kw))[1],
    )

    adapter, repo = _adapter_for(ambient_clone)
    adapter.prepare(repo)
    adapter.prepare(repo)

    assert len(runs) == 1


def test_the_baseline_refuses_a_tree_that_already_carries_a_patch(ambient_clone: Path):
    """The failure mode that has no diagnostic of its own.

    The baseline describes the commit, and `static_verify` subtracts it from its
    own measurement. A modification already in the tree when it is taken is
    therefore subtracted from the verification meant to catch it: the gate
    approves the error it exists to reject and says nothing at all. The graph
    cannot produce this -- `prepare` runs before the patch node, against a fresh
    clone or one `_reset_clone` has put back -- which is why it fails loudly
    instead of being assumed.
    """
    (ambient_clone / "src" / "billing.ts").write_text(
        "export const amount: number = 'free';\n", encoding="utf-8"
    )
    adapter, repo = _adapter_for(ambient_clone)

    with pytest.raises(RuntimeError, match="uncommitted"):
        adapter.prepare(repo)
