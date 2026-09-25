"""Application Insights, through the Azure Monitor OpenTelemetry distro.

Ported from APEX's backend/telemetry.py. On only when
APPLICATIONINSIGHTS_CONNECTION_STRING is set -- the SDK's own variable name.
Unset, nothing is imported and nothing is sent, so local runs and the test
suite are unchanged. A malformed connection string raises from the SDK and the
app refuses to start.
"""
import os

ENV = "APPLICATIONINSIGHTS_CONNECTION_STRING"

# Probed constantly by the Container Apps health checks; not worth recording.
EXCLUDED_URLS = "api/health"

# configure_azure_monitor installs process-wide exporters; a second call
# would add a second set and send everything twice.
_configured = False


def init_app(app) -> bool:
    """Turn telemetry on for `app` if configured. Returns whether it is on."""
    global _configured
    conn = os.environ.get(ENV, "").strip()
    if not conn:
        return False

    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.flask import FlaskInstrumentor

    if not _configured:
        # Flask off here and instrumented per app below: the distro's Flask
        # support patches the Flask class, and app/__init__.py imported Flask
        # before this runs, so the patch would never reach our app.
        configure_azure_monitor(
            connection_string=conn,
            instrumentation_options={"flask": {"enabled": False}},
        )
        _configured = True
    FlaskInstrumentor().instrument_app(app, excluded_urls=EXCLUDED_URLS)
    return True
