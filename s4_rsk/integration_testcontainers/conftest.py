from urllib.parse import unquote, urlparse

import pytest
from django.conf import settings


@pytest.fixture(scope="session")
def postgres_container():
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        "postgres:16-alpine",
        username="test_user",
        password="test_password",
        dbname="testcontainers_db",
        driver=None,
    ) as postgres:
        yield postgres


@pytest.fixture(scope="session")
def django_db_modify_db_settings(postgres_container):
    url = urlparse(postgres_container.get_connection_url())

    settings.DATABASES["default"].update(
        {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(url.path.lstrip("/")),
            "USER": unquote(url.username or ""),
            "PASSWORD": unquote(url.password or ""),
            "HOST": url.hostname,
            "PORT": str(url.port),
            "CONN_MAX_AGE": 0,
        }
    )
