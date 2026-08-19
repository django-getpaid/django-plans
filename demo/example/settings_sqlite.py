"""Test settings for running the suite without a PostgreSQL server.

CI runs the real matrix against PostgreSQL; this module exists so that
manage.py test works on a bare checkout:

    DJANGO_SETTINGS_MODULE=example.settings_sqlite PYTHONPATH=demo \
        python demo/manage.py test plans

The concurrency test cases and length-constraint assertions need a real
PostgreSQL and are expected to fail on SQLite.
"""

from example.settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
