"""Findings from what the vendor actually sent, rather than from what they published.

Every other detector in this system starts from a vendor artifact: a specification diff, a
deprecation table, a release note. This one starts from traffic, which is why it can fire on a
change nobody announced and before anything has broken. Specification diffing sees only what
vendors publish; error-triggered tools see only what has already failed.

It is also the detector most able to violate precision-over-recall, because traffic is noisy in
ways a specification is not. Three rules hold it to the committed position.

The sample floor
----------------
A shape seen fewer than `MIN_SAMPLES` times is not a baseline and is skipped however large the
divergence looks. `vendor_change` refuses to pick a depth cut-off because there is no labelled
data to calibrate one against, and that objection is right; the difference here is that this
threshold has a distribution-free justification rather than a guessed one. By the rule of three,
an outcome not seen in 30 independent samples has a 95% upper bound of about 3/30 -- ten per cent
-- so 30 is roughly the smallest sample at which "the declared shape did not appear" is worth
saying at all. Below it, one upstream incident or one misbehaving account supplies the whole
count. It is a floor on the *divergent* row, not on the operation: a rare field that genuinely
drifts stays silent until it has been seen enough times to be a baseline, which is the intended
trade.

Absence is not evidence
-----------------------
A field the specification marks required and traffic never carries is *not* reported. A field can
be missing from a sample for reasons that have nothing to do with a contract -- an endpoint whose
expansion parameter was never passed, a nullable parent, a customer whose account does not
produce it. Every positive observation this module acts on is something traffic actually
contained.

Severity says what the finding rests on
---------------------------------------
A divergence corroborated by the baseline's own history -- the field arrived one way before and
another way now -- is a change in the vendor's behaviour, and is reported as breaking. An
uncorroborated divergence, where traffic has only ever disagreed with the specification, is far
more likely to be a specification that was always inaccurate, and is reported as information. The
distinction cannot live anywhere but severity, because both produce the same divergence.

That comparison -- observed now against observed before -- never raises a finding by itself. A
baseline that shifts between windows in a way the specification permits is silent. It is
enrichment of a divergence found against the specification, exactly as the spec sequences it.

The enum case this cannot detect
--------------------------------
The spec lists "an enum value the spec does not name" among the divergences to catch, and also
requires that any observed value the published specification does not name be discarded at the
observation boundary. Both cannot hold from `spec_enum_values` alone: the column can only ever
contain published members, so an unpublished member leaves no trace to detect. The privacy rule
is a threat-model commitment and wins; this module therefore detects type drift, nullability
drift and undeclared fields, and does not detect unpublished enum members. Closing that gap
needs a counter of observations whose value was discarded -- a count, never a value -- which is a
schema change to `observed_shape` and is not made here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from sync.core import CallSite, Finding, ObservedShape
from sync.detect.vendor_change import _leads_into
from sync.graph.store import GraphStore

MIN_SAMPLES = 30
"""Observations of one shape below which the detector stays silent. See the module docstring."""


@dataclass(frozen=True)
class DeclaredField:
    """What the vendor's published specification says about one response field.

    Addressed by JSON Pointer, the same form `ObservedShape.field_path` uses, so the two sides
    compare without a translation nobody can verify.

    The component that parses a specification into these is `cli._declared_response_fields`,
    which sits above this module: a detector importing a CLI symbol inverts the dependency, so
    a parser existing is not on its own a reason to move the type. The home that would serve
    both is `sync.core`, and that is a published contract a third party writing a vendor
    adapter depends on -- putting a detector's type into it is a decision about that contract,
    and it has not been made.
    """

    field_path: str
    json_types: frozenset[str]
    """Every type the specification permits. A union declares more than one, and traffic showing
    any of them is the specification being obeyed."""

    required: bool
    nullable: bool


def _segments(field_path: str) -> list[str]:
    """A JSON Pointer as the segment list the call-site matcher compares against."""
    return [segment for segment in field_path.split("/") if segment]


class ObservedDriftDetector:
    """Response shapes that disagree with the specification the vendor published."""

    detector_id = "observed-drift"

    def __init__(
        self,
        store: GraphStore,
        spec: Mapping[str, Sequence[DeclaredField]],
        vendor_id: str = "stripe",
        repo_id: str | None = None,
    ) -> None:
        self._store = store
        self._spec = spec
        self._vendor_id = vendor_id
        # Which repository this scan is about. None means every one of them.
        # `GraphStore.call_sites_for_operation` carries what that cost and why it stays available.
        self._repo_id = repo_id
        self.declined: list[str] = []
        """Divergences this scan did not report, each naming its subject and its cause.

        Three reach it: a baseline no indexed call site resolves to, a divergence under the
        sample floor, and a divergence in a field no call site reads. The second is the whole
        of this detector's output today -- the live baseline holds one row carrying one sample
        -- and a number is what makes that answerable without lowering `MIN_SAMPLES` and
        re-running a scan.

        An operation the specification declares and traffic has never touched is not here. That
        branch fires once per declared operation, so counting it would report the size of the
        vendor's specification on every run, and it cannot distinguish an operation the
        customer calls and has no traffic for from one the customer never calls -- separating
        those needs the call-site query the branch exists to avoid running.
        """

    def scan(self) -> Iterable[Finding]:
        """Every finding, as a list rather than a generator.

        Eager because `declined` is only true once the scan has run, and a generator nobody
        finished consuming would leave the count describing part of the work.
        """
        self.declined = []
        findings: list[Finding] = []

        for operation_id, declared_fields in self._spec.items():
            shapes = self._store.observed_shapes(self._vendor_id, operation_id)
            if not shapes:
                continue

            # A `Finding` addresses its call site by id, so an operation nothing calls has no
            # location to report and no patch to propose.
            sites = self._store.call_sites_for_operation(
                self._vendor_id, operation_id, repo_id=self._repo_id
            )
            if not sites:
                self.declined.append(
                    f"{operation_id}: {len(shapes)} observed shape(s) and no indexed call site "
                    f"resolves to the operation, so a divergence has no location to report"
                )
                continue

            declared = {field.field_path: field for field in declared_fields}
            by_path: dict[str, list[ObservedShape]] = defaultdict(list)
            for shape in shapes:
                by_path[shape.field_path].append(shape)

            for shape in shapes:
                field = declared.get(shape.field_path)
                # Computed before the floor is applied, because whether a thin shape was a
                # finding the floor cost is exactly what the count below has to know.
                divergence = None if field is None else self._divergence(shape, field)

                if shape.sample_count < MIN_SAMPLES:
                    if field is None or divergence is not None:
                        self.declined.append(
                            f"{operation_id} {shape.field_path}: "
                            f"{divergence or 'is not described by the specification'}, seen "
                            f"{shape.sample_count} time(s) against a floor of {MIN_SAMPLES}"
                        )
                    continue

                if field is None:
                    findings.extend(self._undeclared(shape, sites, operation_id))
                    continue

                if divergence is None:
                    continue

                reported = list(self._diverged(
                    shape, field, divergence, by_path[shape.field_path], sites, operation_id
                ))
                if not reported:
                    self.declined.append(
                        f"{operation_id} {shape.field_path}: {divergence}, and no indexed call "
                        f"site reads the field"
                    )
                findings.extend(reported)

        return findings

    def _divergence(self, shape: ObservedShape, field: DeclaredField) -> str | None:
        """How this shape disagrees with what the vendor declared, or `None` if it does not.

        Null is tested before type, because a null arriving where a value is required is a
        statement about the value's presence rather than about its type, and reporting it as
        "the type became null" would send a reviewer looking for a type change that never
        happened.
        """
        if shape.json_type == "null" or shape.nullable_seen:
            if field.required and not field.nullable:
                return "arrives null where the specification requires a value"
            return None

        if shape.json_type not in field.json_types:
            declared = " or ".join(sorted(field.json_types))
            return f"arrives as {shape.json_type} where the specification declares {declared}"

        return None

    def _undeclared(
        self, shape: ObservedShape, sites: Sequence[CallSite], operation_id: str
    ) -> Iterable[Finding]:
        """A field in traffic the specification never mentions.

        No read filter applies: code cannot read a field it was never told about, so requiring a
        call site to touch it would discard every instance of the one case this detector is most
        uniquely able to see. It breaks nothing today, which is what keeps it an addition.
        """
        for site in sites:
            if site.id is None:
                continue
            yield Finding(
                detector=self.detector_id,
                # Static, and the distinction is the point: the binding is static and the
                # evidence is observed. A wrong static binding makes this claim wrong; a
                # correct binding meeting a surprising shape is the finding working.
                binding_rung="static",
                # The field path, because a response with three undescribed fields is three
                # claims a reviewer acts on separately. Bounded by the response schema, so it
                # discriminates without turning traffic volume into rows.
                claim=f"undescribed-field:{shape.field_path}",
                call_site_id=site.id,
                severity="addition",
                rationale=(
                    f"`{shape.field_path}` appears in {operation_id} responses and the "
                    f"specification does not describe it. "
                    + self._evidence(shape)
                ),
            )

    def _diverged(
        self,
        shape: ObservedShape,
        field: DeclaredField,
        divergence: str,
        siblings: Sequence[ObservedShape],
        sites: Sequence[CallSite],
        operation_id: str,
    ) -> Iterable[Finding]:
        """One divergence, reported against the call sites it can actually reach.

        A call site that never reads the field cannot be broken by it, so it is not told. This
        is the same filter `vendor_change` applies for a resolved change path, and the same
        trade: a divergence in a response field nobody consumes is real and is not actionable.
        """
        wanted = _segments(shape.field_path)
        changed = self._contradicts_earlier_window(shape, siblings)

        for site in sites:
            if site.id is None:
                continue
            if not any(_leads_into(read, wanted) for read in site.response_fields_read):
                continue

            yield Finding(
                detector=self.detector_id,
                # Static, and the distinction is the point: the binding is static and the
                # evidence is observed. A wrong static binding makes this claim wrong; a
                # correct binding meeting a surprising shape is the finding working.
                binding_rung="static",
                # Separate from the undescribed-field claim above even for the same path: one
                # says the specification never mentioned the field, the other says it did and
                # traffic disagrees. Two different reports, two different fixes.
                claim=f"shape-drift:{shape.field_path}",
                call_site_id=site.id,
                # Corroborated by the baseline's own history, this is the vendor's behaviour
                # changing. Uncorroborated, it is more likely a specification that was always
                # inaccurate, and claiming otherwise would spend trust the finding has not
                # earned.
                severity="breaking" if changed else "info",
                rationale=self._rationale(shape, field, divergence, changed, site, operation_id),
            )

    def _contradicts_earlier_window(
        self, shape: ObservedShape, siblings: Sequence[ObservedShape]
    ) -> bool:
        """Whether this field was seen behaving differently before this shape first appeared.

        Derived from the baseline that already exists rather than from a second query: a sibling
        row for the same field with an earlier `first_seen` is the earlier window, and its
        existence is what separates "the vendor changed something" from "the specification has
        always been wrong about this field".
        """
        return any(
            sibling.first_seen < shape.first_seen
            for sibling in siblings
            if sibling.json_type != shape.json_type
        )

    def _evidence(self, shape: ObservedShape) -> str:
        """What the claim is made of, in the terms a reviewer would need to discount it."""
        return (
            f"Observed {shape.sample_count} time(s) from {shape.source} between "
            f"{shape.first_seen:%Y-%m-%d} and {shape.last_seen:%Y-%m-%d}."
        )

    def _rationale(
        self,
        shape: ObservedShape,
        field: DeclaredField,
        divergence: str,
        changed: bool,
        site: CallSite,
        operation_id: str,
    ) -> str:
        """What a reviewer needs in order to judge a claim the detector cannot prove."""
        history = (
            "The same field was seen arriving differently before this shape appeared, so the "
            "vendor's behaviour changed rather than the specification having always been wrong."
            if changed
            else "No earlier observation shows this field behaving differently, so an inaccurate "
            "specification is at least as likely an explanation as a change in behaviour."
        )

        return (
            f"`{field.field_path}` on {operation_id} {divergence}, and the call site at "
            f"{site.path}:{site.line} reads it. {self._evidence(shape)} {history} "
            "This rests on observed traffic, not on anything the vendor published: a sample "
            "can misrepresent a rollout in progress, and no specification says this changed."
        )
