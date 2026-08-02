"""A gate that cannot reach its inputs is not a gate, and this one could not for its whole life.

`scripts/score_corpus.py` reads two frozen inputs. The trees come from
`scripts/fetch_corpus_repositories.py`, which CI has always run. The symbol map comes from
`.cache/specs/`, which is gitignored and which no step staged -- so every time the workflow got
as far as scoring it was refused with `no symbol map at .cache/specs/symbols.json`, and the
binding floors below it have never been measured on a runner. The fetch step failing for longer
is what kept that invisible.

The failure mode this pins is not "a step was deleted". It is a step order that looks right and
stages nothing, which reads as a passing job on any run where the gate is never reached. So the
assertions are on position within the job that scores, not on the workflow containing the words
somewhere.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"

SCORER = "scripts/score_corpus.py"

# Everything the scorer reads that a checkout does not carry, and the script that produces it.
# `fetch_corpus_repositories.py` is here too: it has never been the missing one, and a test that
# only names the input that broke would let the next deletion through.
STAGERS = (
    "scripts/fetch_corpus_repositories.py",
    "scripts/fetch_measurement_inputs.py",
    "scripts/stage_symbol_map.py",
)


def _scoring_jobs() -> list[tuple[str, list[dict]]]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return [
        (name, job.get("steps", []))
        for name, job in workflow["jobs"].items()
        if any(SCORER in (step.get("run") or "") for step in job.get("steps", []))
    ]


def _index_of(steps: list[dict], script: str) -> int | None:
    for position, step in enumerate(steps):
        if script in (step.get("run") or ""):
            return position
    return None


def test_ci_scores_the_frozen_corpus_at_all():
    assert _scoring_jobs(), (
        f"no job in ci.yml runs {SCORER}. The binding floors are the only quality number this "
        "repository gates on, and with this step gone nothing measures them"
    )


def test_every_input_the_scorer_reads_is_staged_before_it_runs():
    for job_name, steps in _scoring_jobs():
        scores_at = _index_of(steps, SCORER)
        for script in STAGERS:
            stages_at = _index_of(steps, script)
            assert stages_at is not None, (
                f"job {job_name!r} scores the corpus and never runs {script}. The scorer reads "
                f"what it produces out of gitignored space, so on a runner that input is absent "
                f"and the gate refuses instead of measuring"
            )
            assert stages_at < scores_at, (
                f"job {job_name!r} runs {script} after {SCORER}, so the scorer reads whatever "
                f"was there before it -- on a fresh checkout, nothing"
            )
