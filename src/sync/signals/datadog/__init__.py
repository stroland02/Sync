"""Datadog error and trace payloads as a source of observed response shapes."""

from sync.signals.datadog.shapes import (
    ARRAY_ELEMENT,
    DEFAULT_BODY_ATTRIBUTE,
    SOURCE,
    DatadogShapeReader,
)

__all__ = ["ARRAY_ELEMENT", "DEFAULT_BODY_ATTRIBUTE", "SOURCE", "DatadogShapeReader"]
