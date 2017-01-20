from django.apps import AppConfig

class PlansConfig(AppConfig):

    name = "plans"
    label = "plans"
    verbose_name = "Django Plans"

    def ready(self):

        import plans.listeners
