from django.apps import AppConfig
from django.core.checks import register

from . import conf as app_settings
from .checks import check_country_lookup


class PlansConfig(AppConfig):
    name = "plans"
    verbose_name = app_settings.APP_VERBOSE_NAME

    def ready(self):
        # noinspection PyUnresolvedReferences
        import plans.listeners  # noqa

        register(check_country_lookup)
