"""Thin OpenTelemetry setup. Spans wrap the existing seams (run / feed fetch /
model turn / tool call) and export via OTLP when OTEL_EXPORTER_OTLP_ENDPOINT
is set (e.g. the compose jaeger profile), otherwise to a JSONL file under
state/runs/ so scheduled runs keep their traces."""

from __future__ import annotations

import json
import os
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

def _file_export_path() -> Path:
    return Path(os.environ.get("HADR_SPANS_FILE", "state/runs/spans.jsonl"))


class FileSpanExporter(SpanExporter):
    def export(self, spans) -> SpanExportResult:
        # resolve per export so HADR_SPANS_FILE can change within one process
        path = _file_export_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            for s in spans:
                f.write(
                    json.dumps(
                        {
                            "name": s.name,
                            "start_ns": s.start_time,
                            "duration_ms": (s.end_time - s.start_time) // 1_000_000,
                            "attributes": dict(s.attributes or {}),
                            "status": str(s.status.status_code.name),
                        }
                    )
                    + "\n"
                )
        return SpanExportResult.SUCCESS


_configured = False


def tracer() -> trace.Tracer:
    global _configured
    if not _configured:
        provider = TracerProvider(resource=Resource.create({"service.name": "hadr-claw"}))
        if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            exporter: SpanExporter = OTLPSpanExporter()
        else:
            exporter = FileSpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _configured = True
    return trace.get_tracer("hadr-claw")
