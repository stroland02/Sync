"""Outcome tool schemas and server-side validators for the resolution agent.

This module enforces:
1. Flat schemas only (no top-level oneOf/allOf/anyOf).
2. Server-side validation with model-directed error messages.
3. Retired tool name redirection with actionable guidance.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from sync.core.outcomes import (
    Abandonment,
    Citation,
    ExternalCauseReport,
    FindingsReport,
    HumanQuestion,
    PatchProposal,
    parse_citation,
    validate_confidence,
)

REPORT_FINDINGS_SCHEMA: dict[str, Any] = {
    "name": "report_findings",
    "description": (
        "Report intermediate diagnostic findings and root cause hypothesis. "
        "Non-terminal: callable repeatedly as new evidence is gathered."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "High-level summary of findings",
            },
            "root_cause": {
                "type": "string",
                "description": "Diagnosed root cause mechanism",
            },
            "confidence": {
                "type": "integer",
                "description": "Calibrated confidence score from 1 (speculative) to 10 (reproduced and verified)",
            },
            "estimated_impact": {
                "type": "string",
                "description": "Optional blast radius or runtime impact description",
            },
        },
        "required": ["summary", "root_cause", "confidence"],
    },
}

PROPOSE_PATCH_SCHEMA: dict[str, Any] = {
    "name": "propose_patch",
    "description": (
        "Propose a verified patch to resolve the API finding. "
        "Terminal outcome: ends the agent resolution turn."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "diff": {
                "type": "string",
                "description": "Unified diff of changes to apply",
            },
            "strategy": {
                "type": "string",
                "enum": ["agent", "codemod"],
                "description": "Strategy applied: 'agent' or 'codemod'",
            },
            "rationale": {
                "type": "string",
                "description": "Explanation of how the patch resolves the finding",
            },
            "confidence": {
                "type": "integer",
                "description": "Calibrated confidence score (1 to 10)",
            },
            "citations": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of citations backing the patch in format:\n"
                    "path/to/file:line\n```lang\ncode\n```"
                ),
            },
        },
        "required": ["diff", "strategy", "rationale", "confidence", "citations"],
    },
}

REPORT_EXTERNAL_CAUSE_SCHEMA: dict[str, Any] = {
    "name": "report_external_cause",
    "description": (
        "Report that the failure is caused by an external vendor condition "
        "(e.g. vendor outage, decommissioned endpoint, sandbox error). "
        "Terminal outcome: distinguishes external factors from code defects."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Summary of external condition",
            },
            "cause": {
                "type": "string",
                "description": "Detailed explanation of the external condition",
            },
            "vendor": {
                "type": "string",
                "description": "Optional vendor identifier",
            },
            "external_url": {
                "type": "string",
                "description": "Optional URL to status page or vendor changelog incident",
            },
            "confidence": {
                "type": "integer",
                "description": "Calibrated confidence score (1 to 10)",
            },
            "citations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of citations demonstrating call site impact",
            },
        },
        "required": ["summary", "cause", "confidence", "citations"],
    },
}

ASK_HUMAN_SCHEMA: dict[str, Any] = {
    "name": "ask_human",
    "description": (
        "Park the resolution run to ask an operator/user a clarifying question. "
        "Terminal outcome: suspends run until human responds."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Clear, specific question for the human operator",
            },
            "context": {
                "type": "string",
                "description": "Background context and trade-offs",
            },
            "blocking": {
                "type": "boolean",
                "description": "Whether resolution cannot proceed without human response",
            },
            "confidence": {
                "type": "integer",
                "description": "Calibrated confidence score (1 to 10)",
            },
            "citations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of citations establishing the ambiguity",
            },
        },
        "required": ["question", "context", "confidence", "citations"],
    },
}

ABANDON_SCHEMA: dict[str, Any] = {
    "name": "abandon",
    "description": (
        "Abandon automated remediation with a coded reason. "
        "Terminal outcome: records structured abandonment for corpus analytics."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason_code": {
                "type": "string",
                "description": "Coded identifier for abandonment reason (e.g. 'unsupported_sdk_version')",
            },
            "explanation": {
                "type": "string",
                "description": "Detailed explanation of why remediation was abandoned",
            },
            "confidence": {
                "type": "integer",
                "description": "Calibrated confidence score (1 to 10)",
            },
            "citations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of citations supporting abandonment",
            },
        },
        "required": ["reason_code", "explanation", "confidence", "citations"],
    },
}

OUTCOME_TOOL_SCHEMAS: tuple[dict[str, Any], ...] = (
    REPORT_FINDINGS_SCHEMA,
    PROPOSE_PATCH_SCHEMA,
    REPORT_EXTERNAL_CAUSE_SCHEMA,
    ASK_HUMAN_SCHEMA,
    ABANDON_SCHEMA,
)

RETIRED_OUTCOME_TOOL_NAMES: dict[str, str] = {
    "submit_patch": "The tool 'submit_patch' has been renamed to 'propose_patch'. Please call 'propose_patch' with {diff, strategy, rationale, confidence, citations}.",
    "report_outage": "The tool 'report_outage' has been renamed to 'report_external_cause'. Please call 'report_external_cause' with {summary, cause, vendor, external_url, confidence, citations}.",
    "ask_user": "The tool 'ask_user' has been renamed to 'ask_human'. Please call 'ask_human' with {question, context, blocking, confidence, citations}.",
    "give_up": "The tool 'give_up' has been renamed to 'abandon'. Please call 'abandon' with {reason_code, explanation, confidence, citations}.",
}


class OutcomeValidationResult(BaseModel):
    ok: bool
    error: str | None = None
    payload: Any = None


class OutcomeToolValidator:
    """Validates outcome tool arguments server-side."""

    @staticmethod
    def validate(tool_name: str, arguments: dict[str, Any]) -> OutcomeValidationResult:
        if tool_name in RETIRED_OUTCOME_TOOL_NAMES:
            return OutcomeValidationResult(
                ok=False,
                error=RETIRED_OUTCOME_TOOL_NAMES[tool_name],
            )

        if tool_name == "report_findings":
            return OutcomeToolValidator._validate_report_findings(arguments)
        if tool_name == "propose_patch":
            return OutcomeToolValidator._validate_propose_patch(arguments)
        if tool_name == "report_external_cause":
            return OutcomeToolValidator._validate_report_external_cause(arguments)
        if tool_name == "ask_human":
            return OutcomeToolValidator._validate_ask_human(arguments)
        if tool_name == "abandon":
            return OutcomeToolValidator._validate_abandon(arguments)

        return OutcomeValidationResult(
            ok=False,
            error=f"Unknown outcome tool '{tool_name}'. Available outcome tools: report_findings, propose_patch, report_external_cause, ask_human, abandon.",
        )

    @staticmethod
    def _validate_citations(raw_citations: Any) -> tuple[list[Citation] | None, str | None]:
        if not isinstance(raw_citations, list) or len(raw_citations) == 0:
            return None, "Citations must be a non-empty list of citation strings with 'path:line' format and fenced code quotes."
        parsed: list[Citation] = []
        for item in raw_citations:
            if not isinstance(item, str):
                return None, f"Invalid citation item {item!r}; must be a formatted citation string."
            try:
                citation = parse_citation(item)
                parsed.append(citation)
            except ValueError as e:
                return None, f"Invalid citation format: {e}"
        return parsed, None

    @staticmethod
    def _validate_report_findings(args: dict[str, Any]) -> OutcomeValidationResult:
        summary = args.get("summary")
        root_cause = args.get("root_cause")
        confidence = args.get("confidence")
        if not summary or not isinstance(summary, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'summary' field in report_findings.")
        if not root_cause or not isinstance(root_cause, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'root_cause' field in report_findings.")
        ok_conf, err_conf = validate_confidence(confidence)
        if not ok_conf:
            return OutcomeValidationResult(ok=False, error=err_conf)

        return OutcomeValidationResult(
            ok=True,
            payload=FindingsReport(
                summary=summary,
                root_cause=root_cause,
                confidence=confidence,
                estimated_impact=args.get("estimated_impact"),
            ),
        )

    @staticmethod
    def _validate_propose_patch(args: dict[str, Any]) -> OutcomeValidationResult:
        diff = args.get("diff")
        strategy = args.get("strategy")
        rationale = args.get("rationale")
        confidence = args.get("confidence")
        raw_citations = args.get("citations")

        if not diff or not isinstance(diff, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'diff' field in propose_patch.")
        if strategy not in ("agent", "codemod"):
            return OutcomeValidationResult(ok=False, error=f"Invalid strategy '{strategy}' in propose_patch. Must be 'agent' or 'codemod'.")
        if not rationale or not isinstance(rationale, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'rationale' field in propose_patch.")
        ok_conf, err_conf = validate_confidence(confidence)
        if not ok_conf:
            return OutcomeValidationResult(ok=False, error=err_conf)

        citations, err_cit = OutcomeToolValidator._validate_citations(raw_citations)
        if err_cit:
            return OutcomeValidationResult(ok=False, error=err_cit)

        return OutcomeValidationResult(
            ok=True,
            payload=PatchProposal(
                diff=diff,
                strategy=strategy,
                rationale=rationale,
                confidence=confidence,
                citations=citations,
            ),
        )

    @staticmethod
    def _validate_report_external_cause(args: dict[str, Any]) -> OutcomeValidationResult:
        summary = args.get("summary")
        cause = args.get("cause")
        confidence = args.get("confidence")
        raw_citations = args.get("citations")

        if not summary or not isinstance(summary, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'summary' field in report_external_cause.")
        if not cause or not isinstance(cause, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'cause' field in report_external_cause.")
        ok_conf, err_conf = validate_confidence(confidence)
        if not ok_conf:
            return OutcomeValidationResult(ok=False, error=err_conf)

        citations, err_cit = OutcomeToolValidator._validate_citations(raw_citations)
        if err_cit:
            return OutcomeValidationResult(ok=False, error=err_cit)

        return OutcomeValidationResult(
            ok=True,
            payload=ExternalCauseReport(
                summary=summary,
                cause=cause,
                vendor=args.get("vendor"),
                external_url=args.get("external_url"),
                confidence=confidence,
                citations=citations,
            ),
        )

    @staticmethod
    def _validate_ask_human(args: dict[str, Any]) -> OutcomeValidationResult:
        question = args.get("question")
        context = args.get("context")
        confidence = args.get("confidence")
        raw_citations = args.get("citations")

        if not question or not isinstance(question, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'question' field in ask_human.")
        if not context or not isinstance(context, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'context' field in ask_human.")
        ok_conf, err_conf = validate_confidence(confidence)
        if not ok_conf:
            return OutcomeValidationResult(ok=False, error=err_conf)

        citations, err_cit = OutcomeToolValidator._validate_citations(raw_citations)
        if err_cit:
            return OutcomeValidationResult(ok=False, error=err_cit)

        return OutcomeValidationResult(
            ok=True,
            payload=HumanQuestion(
                question=question,
                context=context,
                blocking=args.get("blocking", True),
                confidence=confidence,
                citations=citations,
            ),
        )

    @staticmethod
    def _validate_abandon(args: dict[str, Any]) -> OutcomeValidationResult:
        reason_code = args.get("reason_code")
        explanation = args.get("explanation")
        confidence = args.get("confidence")
        raw_citations = args.get("citations")

        if not reason_code or not isinstance(reason_code, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'reason_code' field in abandon.")
        if not explanation or not isinstance(explanation, str):
            return OutcomeValidationResult(ok=False, error="Missing or invalid 'explanation' field in abandon.")
        ok_conf, err_conf = validate_confidence(confidence)
        if not ok_conf:
            return OutcomeValidationResult(ok=False, error=err_conf)

        citations, err_cit = OutcomeToolValidator._validate_citations(raw_citations)
        if err_cit:
            return OutcomeValidationResult(ok=False, error=err_cit)

        return OutcomeValidationResult(
            ok=True,
            payload=Abandonment(
                reason_code=reason_code,
                explanation=explanation,
                confidence=confidence,
                citations=citations,
            ),
        )


def validate_outcome_call(tool_name: str, arguments: dict[str, Any]) -> OutcomeValidationResult:
    """Convenience helper to validate an outcome tool invocation."""
    return OutcomeToolValidator.validate(tool_name, arguments)
