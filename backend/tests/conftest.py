"""Configure application settings before test modules import the app."""
from contextlib import contextmanager
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

os.environ.setdefault("DEMO_MODE", "true")
os.environ["LLM_PROVIDER"] = "mock"

APP_DB_ENV = "SENTRAX_APP_TEST_DATABASE_URL"


def disposable_url(variable):
    value = os.getenv(variable)
    if not value:
        return None
    error = f"{variable} must name a disposable PostgreSQL database ending in _test"
    try:
        url = make_url(value)
    except ArgumentError:
        raise pytest.UsageError(error) from None
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test") or "dbname" in url.query:
        raise pytest.UsageError(error)
    return url


app_url = disposable_url(APP_DB_ENV)
if app_url is not None:
    os.environ["DATABASE_URL"] = app_url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    os.environ["DATABASE_URL_ASYNC"] = app_url.set(drivername="postgresql+psycopg_async").render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def application_test_database():
    if app_url is None:
        pytest.skip(f"set {APP_DB_ENV} to a disposable migrated and seeded database")


@contextmanager
def disposable_engine(variable):
    url = disposable_url(variable)
    if url is None:
        pytest.skip(f"set {variable} to an explicitly disposable PostgreSQL database")
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def legacy_test_engine():
    with disposable_engine("SENTRAX_LEGACY_TEST_DATABASE_URL") as engine:
        with engine.connect() as connection:
            if connection.scalar(text("SELECT to_regclass('public.alembic_version')")) is not None:
                pytest.fail("SENTRAX_LEGACY_TEST_DATABASE_URL must point to an unmigrated database")
        yield engine


@pytest.fixture(scope="session")
def triage_test_engine():
    with disposable_engine("TEST_DATABASE_URL") as engine:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM alerts LIMIT 1"))
        yield engine


@pytest.fixture(scope="session")
def contributor_test_engine():
    with disposable_engine("SENTRAX_INTEGRATION_DATABASE_URL") as engine:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        yield engine
