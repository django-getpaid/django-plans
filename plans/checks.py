from importlib.util import find_spec

from django.conf import settings
from django.core.checks import Warning


def check_country_lookup(app_configs, **kwargs):
    """Warn when the IP country lookup is on but cannot work.

    Without the ``geolite2`` module ``get_country_code`` falls back to
    ``PLANS_DEFAULT_COUNTRY`` for everyone, so every buyer is taxed as if
    they lived in that country, with no error anywhere.
    """
    if (
        getattr(settings, "PLANS_GET_COUNTRY_FROM_IP", False)
        and getattr(settings, "PLANS_GET_COUNTRY_CODE", None) is None
        and find_spec("geolite2") is None
    ):
        return [
            Warning(
                "PLANS_GET_COUNTRY_FROM_IP is on but the geolite2 module is not "
                "installed, so every buyer gets PLANS_DEFAULT_COUNTRY.",
                hint="Install maxminddb-geolite2, or set PLANS_GET_COUNTRY_CODE "
                "to your own lookup.",
                id="plans.W001",
            )
        ]
    return []
