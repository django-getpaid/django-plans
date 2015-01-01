# TODO use django-conf
from django.conf import settings

TAX = getattr(settings, 'PLANS_TAX', None)
TAXATION_POLICY = getattr(settings,
                          'PLANS_TAXATION_POLICY',
                          'plans.taxation.TAXATION_POLICY')
