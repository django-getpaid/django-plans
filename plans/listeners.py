from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from plans.models import Order, Invoice, BuyerPlan, Plan
from plans.signals import order_completed, activate_buyer_plan
from plans.contrib import get_buyer_model


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


@receiver(post_save, sender=get_buyer_model())
def set_default_buyer_plan(sender, instance, created, **kwargs):
    """
    Creates default plan for the new buyer but also extending an account for default grace period.
    """

    if created:
        default_plan = Plan.get_default_plan()
        if default_plan is not None:
            BuyerPlan.objects.create(buyer=instance, plan=default_plan, active=False, expire=None)


# Hook to django-registration to initialize plan automatically after user has confirm account

@receiver(activate_buyer_plan)
def initialize_plan_generic(sender, buyer, **kwargs):
    try:
        buyer.buyerplan.initialize()
    except BuyerPlan.DoesNotExist:
        return


try:
    from registration.signals import user_activated

    @receiver(user_activated)
    def initialize_plan_django_registration(sender, buyer, request, **kwargs):
        try:
            buyer.buyerplan.initialize()
        except BuyerPlan.DoesNotExist:
            return


except ImportError:
    pass


# Hook to django-getpaid if it is installed
try:
    from getpaid.signals import user_data_query

    @receiver(user_data_query)
    def set_user_email_for_getpaid(sender, order, user_data, **kwargs):
        user_data['email'] = order.buyer.email
except ImportError:
    pass
