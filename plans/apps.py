from django.apps import AppConfig

from . import conf as app_settings


class PlansConfig(AppConfig):
    name = 'plans'
    verbose_name = app_settings.APP_VERBOSE_NAME
