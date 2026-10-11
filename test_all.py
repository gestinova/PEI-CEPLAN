"""Root-level unittest discovery bridge for the backend test suite."""

from backend.test_admin import AdminTests
from backend.test_auth import AuthTests
from backend.test_dashboard import DashboardTests
from backend.test_generation_accounting import GenerationAccountingTests


__all__ = [
    "AdminTests",
    "AuthTests",
    "DashboardTests",
    "GenerationAccountingTests",
]
