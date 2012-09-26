from datetime import date, timedelta
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from plans.models import Order, BillingInfo, Invoice
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

