from datetime import date, timedelta, datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from pytz import utc
from plans.models import Order, Invoice, UserPlan, Plan
from plans.signals import order_completed

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
    if created:
        default_plan = Plan.get_default_plan()
        if default_plan is not None:
            UserPlan.objects.create(user=instance,
                                    plan=default_plan,
                                    active=True,
                                    expire=datetime.utcnow().replace(tzinfo=utc) +
                                           timedelta(days=getattr(settings, 'PLAN_DEFAULT_GRACE_PERIOD', 30)))
