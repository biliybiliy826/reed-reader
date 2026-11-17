import os

# Never register global keys or access a real user data directory in unit/GUI tests.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from .test_legado import service  # noqa: E402,F401 -- register the shared HTTP fixture
