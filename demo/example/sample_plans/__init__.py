try:
    import django

    if django.VERSION < (3, 2):
        default_app_config = 'example.sample_plans.apps.SamplePlansConfig'
except ImportError:
    pass
