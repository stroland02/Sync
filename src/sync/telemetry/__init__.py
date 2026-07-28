"""Runtime telemetry: turning a customer's client spans into observed vendor calls.

This package knows about OTLP and about HTTP. It does not know about any vendor. Which
operation a request addresses is a question only a vendor adapter can answer, and it is asked
through `sync.core.protocols.RequestCorrelator` rather than by importing one.
"""

from sync.telemetry.ingest import IngestReport, ingest_payload
from sync.telemetry.otlp import client_spans

__all__ = ["IngestReport", "client_spans", "ingest_payload"]
