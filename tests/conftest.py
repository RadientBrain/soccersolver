import os
import pytest

# Ensure DATABASE_URL is set for all tests
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://soccer:soccer123@localhost:5432/soccersolver"
)


def pytest_configure(config):
    """Register markers."""
    config.addinivalue_line("markers", "integration: marks tests that require a live DB")


def pytest_collection_modifyitems(items):
    """All tests in test_integration.py are integration tests."""
    for item in items:
        if "test_integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
