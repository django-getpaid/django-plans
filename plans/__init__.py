__version__ = '0.8.13'

try:
    import django

    if django.VERSION < (3, 2):
        default_app_config = 'plans.apps.PlansConfig'
except ImportError:
    pass
