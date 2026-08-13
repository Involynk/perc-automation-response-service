import pytest
from app.core.config import settings, Settings


def test_config_loading():
    assert settings.DATABASE_URL is not None
    assert len(settings.DATABASE_URL) > 0
    assert settings.ENVIRONMENT == "development"


def test_empty_database_url_rejected():
    with pytest.raises(ValueError):
        Settings(DATABASE_URL="", ENVIRONMENT="test")
