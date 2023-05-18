__version__ = '1.0.4'

try:
    import django

    if django.VERSION < (3, 2):
        default_app_config = 'plans.apps.PlansConfig'
except ImportError:
    pass
