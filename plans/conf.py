# TODO use django-conf
from django.conf import settings
from django.apps import apps as django_apps
from django.core.exceptions import ImproperlyConfigured

TAX = getattr(settings, 'PLANS_TAX', None)
TAXATION_POLICY = getattr(settings,
                          'PLANS_TAXATION_POLICY',
                          'plans.taxation.TAXATION_POLICY')
APP_VERBOSE_NAME = getattr(settings, 'PLANS_APP_VERBOSE_NAME', 'plans')


def get_customer_model_string():
    """Get the configured customer model as a module path string."""
    return getattr(settings, "PLAN_CUSTOMER_MODEL", settings.AUTH_USER_MODEL)


def get_customer_model():
    """
    Attempt to pull settings.PLAN_CUSTOMER_MODEL.

    Users have the option of specifying a custom model model via the
    PLAN_CUSTOMER_MODEL setting.

    This methods falls back to AUTH_USER_MODEL if PLAN_CUSTOMER_MODEL setting.  is not set.

    Returns the customer model that is active in this project.
    """
    model_name = get_customer_model_string()

    # Attempt a Django 1.7 app lookup
    try:
        customer_model = django_apps.get_model(model_name)
    except ValueError:
        raise ImproperlyConfigured(
            "PLAN_CUSTOMER_MODEL must be of the form 'app_label.model_name'."
        )
    except LookupError:
        raise ImproperlyConfigured(
            "PLAN_CUSTOMER_MODEL refers to model '{model}' "
            "that has not been installed.".format(model=model_name)
        )

    if (
            "email" not in [field_.name for field_ in customer_model._meta.get_fields()]
    ) and not hasattr(customer_model, "email"):
        raise ImproperlyConfigured(
            "PLAN_CUSTOMER_MODEL must have an email attribute."
        )

    return customer_model
