"""Outcome models, calibration rubric, and citation validation for resolution runs.

This module belongs to sync.core and imports nothing from any sibling package.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, Field

from sync.core.models import PatchStrategy

# Calibration rubric for confidence integers (1..10)
# 10: Every claim is backed by a verbatim quote from a file read this session AND the failure was reproduced.
# 7-9: Code path verified, exact patch mechanics proven by static analysis/reproduction.
# 4-6: Code path is identified and the mechanism is a hypothesis.
# 1-3: Speculative or incomplete evidence.
CONFIDENCE_RUBRIC: dict[int, str] = {
    10: "Every claim is backed by a verbatim quote from a file read this session and the failure was reproduced.",
    9: "Code path verified with verbatim citations and patch mechanics statically proven against the vendor spec.",
    8: "Code path verified with verbatim citations and patch mechanics validated against known vendor changes.",
    7: "Code path identified with citations; change mechanism verified but secondary side-effects unverified.",
    6: "Code path identified with citations; change mechanism is a well-supported hypothesis.",
    5: "Code path identified; mechanism is a plausible hypothesis without full reproduction.",
    4: "Call site located, but root cause or vendor interaction involves unverified assumptions.",
    3: "Speculative root cause with partial citations.",
    2: "Weak correlation between call site and vendor error; insufficient evidence.",
    1: "Speculative or ungrounded claim without verified file citations.",
}


def validate_confidence(score: Any) -> tuple[bool, str | None]:
    """Validate that score is an integer between 1 and 10."""
    if not isinstance(score, int) or isinstance(score, bool):
        return False, "Confidence must be an integer from 1 to 10 according to the calibration rubric."
    if score < 1 or score > 10:
        return False, f"Confidence score {score} is out of bounds. Must be an integer from 1 to 10."
    return True, None


_CITATION_PATTERN = re.compile(
    r"^(?P<path>[^:\n\r]+):(?P<start>\d+)(?:-(?P<end>\d+))?\s*(?:\r?\n)```[a-zA-Z0-9_-]*\r?\n(?P<quote>[\s\S]*?)\r?\n```",
    re.MULTILINE,
)


class Citation(BaseModel):
    """A citation referencing a file, line range, and fenced quote."""

    path: str = Field(description="Relative path to the cited file")
    line: int = Field(description="Starting line number (1-indexed)")
    end_line: int | None = Field(default=None, description="Optional ending line number (inclusive)")
    quote: str = Field(description="Verbatim quoted text from the file")

    def format_citation(self) -> str:
        line_part = f"{self.line}-{self.end_line}" if self.end_line else f"{self.line}"
        return f"{self.path}:{line_part}\n```\n{self.quote}\n```"


def parse_citation(text: str) -> Citation:
    """Parse a citation string in the format:
    path/to/file.ext:14[-20]
    ```lang
    quoted lines
    ```
    """
    text = text.strip()
    match = _CITATION_PATTERN.search(text)
    if not match:
        # Check if missing line number
        if ":" not in text.split("\n")[0]:
            raise ValueError(
                f"Citation header '{text.splitlines()[0] if text else text}' is missing 'path:line' format."
            )
        # Check if missing fenced quote
        if "```" not in text:
            raise ValueError(
                "Citation is missing a fenced code quote (e.g. ```typescript\\n...\\n```)."
            )
        raise ValueError(
            f"Could not parse citation '{text}'. Expected format:\npath/to/file:14\n```lang\nquoted code\n```"
        )

    path = match.group("path").strip()
    start_line = int(match.group("start"))
    end_str = match.group("end")
    end_line = int(end_str) if end_str else None
    quote = match.group("quote")

    return Citation(path=path, line=start_line, end_line=end_line, quote=quote)


class FindingsReport(BaseModel):
    """Non-terminal intermediate findings report produced by the resolution agent."""

    summary: str = Field(description="Summary of the findings")
    root_cause: str = Field(description="Diagnosed root cause")
    confidence: int = Field(description="Confidence integer (1-10) per calibration rubric")
    estimated_impact: str | None = Field(default=None, description="Estimated blast radius or runtime impact")


class PatchProposal(BaseModel):
    """Terminal outcome proposing a verified code patch."""

    diff: str = Field(description="Unified diff of proposed modifications")
    strategy: PatchStrategy = Field(description="Patch strategy: 'agent' or 'codemod'")
    rationale: str = Field(description="Detailed rationale for the patch")
    confidence: int = Field(description="Confidence integer (1-10) per calibration rubric")
    citations: list[Citation] = Field(description="List of verified citations backing the patch")


class ExternalCauseReport(BaseModel):
    """Terminal outcome reporting an external root cause (e.g. vendor outage, decommissioned endpoint)."""

    summary: str = Field(description="Summary of the external cause")
    cause: str = Field(description="Detailed explanation of external factor")
    vendor: str | None = Field(default=None, description="Vendor identifier if known")
    external_url: str | None = Field(default=None, description="Public status page or changelog reference URL")
    confidence: int = Field(description="Confidence integer (1-10) per calibration rubric")
    citations: list[Citation] = Field(description="List of citations demonstrating call site impact")


class HumanQuestion(BaseModel):
    """Terminal outcome parking the run to ask the human an ambiguous question."""

    question: str = Field(description="Specific question to present to the user/operator")
    context: str = Field(description="Context explaining the trade-offs or ambiguity")
    blocking: bool = Field(default=True, description="Whether resolution cannot proceed without human response")
    confidence: int = Field(description="Confidence integer (1-10) per calibration rubric")
    citations: list[Citation] = Field(description="List of citations establishing the ambiguity")


class Abandonment(BaseModel):
    """Terminal outcome abandoning automated remediation."""

    reason_code: str = Field(description="Coded abandonment reason")
    explanation: str = Field(description="Detailed diagnostics and explanation")
    confidence: int = Field(description="Confidence integer (1-10) per calibration rubric")
    citations: list[Citation] = Field(description="List of citations supporting abandonment")
