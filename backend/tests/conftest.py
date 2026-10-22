import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# #region agent log
import json, os, sys, time
from pathlib import Path as _DebugPath

def _agent_dbg(message, data, hypothesis_id, location="backend/tests/conftest.py"):
    payload = {
        "sessionId": "6c2dc2",
        "runId": os.environ.get("DEBUG_RUN_ID", "pre-fix"),
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with open(_DebugPath(r"C:\Users\hp\Desktop\DataAnalystAgentAi\debug-6c2dc2.log"), "a", encoding="utf-8") as _f:
        _f.write(json.dumps(payload) + "\n")

_agent_dbg(
    "conftest_start",
    {
        "cwd": os.getcwd(),
        "sys_path_head": sys.path[:8],
        "app_in_path": any(((_DebugPath(p) / "app").exists() if p else False) for p in sys.path[:12]),
        "import_mode_env": os.environ.get("PYTEST_ADDOPTS", ""),
    },
    "A",
)
try:
    import app as _app_probe  # noqa: F401
    _agent_dbg("app_import_ok", {"app_file": getattr(_app_probe, "__file__", None)}, "A")
except Exception as _exc:
    _agent_dbg("app_import_failed", {"type": type(_exc).__name__, "msg": str(_exc)}, "A")
    raise
# #endregion

import app.models.user  # noqa: F401
import app.models.dataset  # noqa: F401
import app.models.settings  # noqa: F401
import app.models.password_reset  # noqa: F401
from app.database.database import Base, get_db
from app.main import app as fastapi_app

# Isolated in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def pytest_configure(config):
    # #region agent log
    ini_paths = list(getattr(config, "inicfg", {}).get("testpaths", "").split()) if hasattr(config, "inicfg") else []
    try:
        ini_paths = list(config.getini("testpaths") or [])
    except Exception:
        pass
    args = [str(a) for a in config.args]
    pythonpath_ini = None
    try:
        pythonpath_ini = list(config.getini("pythonpath") or [])
    except Exception as exc:
        pythonpath_ini = ["<error>", str(exc)]
    _agent_dbg(
        "pytest_configure",
        {
            "rootdir": str(config.rootpath),
            "inipath": str(getattr(config, "inipath", "")),
            "testpaths": ini_paths,
            "pythonpath_ini": pythonpath_ini,
            "args": args,
            "import_mode": str(config.getoption("importmode", default=None)),
            "cwd": os.getcwd(),
        },
        "B",
        "backend/tests/conftest.py:pytest_configure",
    )
    # #endregion


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh schema for each test and drop afterwards."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Yield a database session for direct model inspection in tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    """TestClient with database dependency overridden to test in-memory SQLite."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
