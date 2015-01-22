from django.apps import AppConfig

class PlansConfig(AppConfig):

    def ready(self):

        import plans.listeners