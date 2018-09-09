from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from plans.models import Order, Invoice, UserPlan, Plan
from plans.signals import order_completed, activate_user_plan


User = get_user_model()


@receiver(post_save, sender=Order)
def create_proforma_invoice(sender, instance, created, **kwargs):
    """
    For every Order if there are defined billing_data creates invoice proforma,
    which is an order confirmation document
    """
    if created:
        Invoice.create(instance, Invoice.INVOICE_TYPES['PROFORMA'])


@receiver(order_completed)
def create_invoice(sender, **kwargs):
    Invoice.create(sender, Invoice.INVOICE_TYPES['INVOICE'])


@receiver(post_save, sender=Invoice)
def send_invoice_by_email(sender, instance, created, **kwargs):
    if created:
        instance.send_invoice_by_email()


@receiver(post_save, sender=User)
def set_default_user_plan(sender, instance, created, **kwargs):
    """
    Creates default plan for the new user but also extending an account for default grace period.
    """

    if created:
        UserPlan.create_for_user(instance)


# Hook to django-registration to initialize plan automatically after user has confirm account

@receiver(activate_user_plan)
def initialize_plan_generic(sender, user, **kwargs):
    try:
        user.userplan.initialize()
    except UserPlan.DoesNotExist:
        return


try:
    from registration.signals import user_activated
    @receiver(user_activated)
    def initialize_plan_django_registration(sender, user, request, **kwargs):
        try:
             user.userplan.initialize()
        except UserPlan.DoesNotExist:
            return


except ImportError:
    pass


# Hook to django-getpaid if it is installed
try:
    from getpaid.signals import user_data_query
    @receiver(user_data_query)
    def set_user_email_for_getpaid(sender, order, user_data, **kwargs):
        user_data['email'] = order.user.email
except ImportError:
    pass
