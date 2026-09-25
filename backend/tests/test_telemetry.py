"""Application Insights is on only when its connection string is set.

The SDK is faked through sys.modules: the real one is only imported when the
variable is set, so it need not be installed for the suite (the container
installs it from requirements.txt).
"""

import sys
import types

import pytest
from flask import Flask

from app import telemetry


@pytest.fixture
def sdk(monkeypatch):
    calls = {"configure": [], "instrument": []}

    monitor = types.ModuleType("azure.monitor.opentelemetry")
    monitor.configure_azure_monitor = lambda **kw: calls["configure"].append(kw)

    flask_inst = types.ModuleType("opentelemetry.instrumentation.flask")

    class FlaskInstrumentor:
        def instrument_app(self, app, **kw):
            calls["instrument"].append((app, kw))

    flask_inst.FlaskInstrumentor = FlaskInstrumentor
    monkeypatch.setitem(sys.modules, "azure.monitor.opentelemetry", monitor)
    monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation.flask", flask_inst)
    monkeypatch.setattr(telemetry, "_configured", False)
    return calls


def test_off_without_a_connection_string(sdk, monkeypatch):
    monkeypatch.delenv(telemetry.ENV, raising=False)
    assert telemetry.init_app(Flask(__name__)) is False
    assert sdk == {"configure": [], "instrument": []}


def test_on_with_a_connection_string(sdk, monkeypatch):
    monkeypatch.setenv(telemetry.ENV, "InstrumentationKey=abc")
    app = Flask(__name__)
    assert telemetry.init_app(app) is True
    assert sdk["configure"][0]["connection_string"] == "InstrumentationKey=abc"
    # Flask is instrumented per app, not via the distro's class patch.
    assert sdk["configure"][0]["instrumentation_options"] == {"flask": {"enabled": False}}
    assert sdk["instrument"] == [(app, {"excluded_urls": "api/health"})]


def test_exporters_are_installed_once(sdk, monkeypatch):
    """configure_azure_monitor is process-wide; a second call would send
    everything twice. Each app is still instrumented."""
    monkeypatch.setenv(telemetry.ENV, "InstrumentationKey=abc")
    telemetry.init_app(Flask(__name__))
    telemetry.init_app(Flask(__name__))
    assert len(sdk["configure"]) == 1
    assert len(sdk["instrument"]) == 2
