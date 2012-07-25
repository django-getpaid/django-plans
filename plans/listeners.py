from datetime import date, timedelta
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from plans.models import Order, BillingInfo, Invoice

@receiver(post_save, sender=Order)
def create_proforma_invoice(sender, instance, created, **kwargs):
    """
    For every Order if there are defined billing_data creates invoice proforma,
    which is an order confirmation document
    """
    if created:
        try:
            billing_info = BillingInfo.objects.get(user=instance.user)
        except BillingInfo.DoesNotExist:
            return

        day = date.today()
        invoice = Invoice(issued=day, selling_date=day, payment_date=day + timedelta(days=14))
        invoice.type = Invoice.INVOICE_TYPES['PROFORMA']
        invoice.copy_from_order(instance)
        invoice.set_issuer_invoice_data()
        invoice.set_buyer_invoice_data(billing_info)
        invoice.clean()
        invoice.save()

