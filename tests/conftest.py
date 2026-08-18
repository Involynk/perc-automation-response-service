import pytest
from app.core.config import settings


@pytest.fixture(autouse=True)
def configure_test_provider(monkeypatch, request):
    """Ensure standard CI and unit tests use deterministic mock provider by default.

    Live tests marked with @pytest.mark.live preserve the active environment settings.
    """
    if "live" not in request.keywords:
        monkeypatch.setattr(settings, "QUERY_UNDERSTANDING_PROVIDER", "mock")
        monkeypatch.setattr("app.agent.nodes.understand.settings.QUERY_UNDERSTANDING_PROVIDER", "mock")
