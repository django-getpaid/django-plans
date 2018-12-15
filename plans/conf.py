# TODO use django-conf
from django.conf import settings

TAX = getattr(settings, 'PLANS_TAX', None)
TAXATION_POLICY = getattr(settings,
                          'PLANS_TAXATION_POLICY',
                          'plans.taxation.TAXATION_POLICY')
APP_VERBOSE_NAME = getattr(settings, 'PLANS_APP_VERBOSE_NAME', 'plans')
