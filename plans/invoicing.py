"""Invoicing jobs the listeners run through ``PLANS_INVOICING_RUNNER``."""

from django.conf import settings
from django.utils.module_loading import import_string

from plans.base.models import AbstractInvoice, AbstractOrder


def run(job, *args):
    """Run ``job(*args)`` now, or hand it to ``PLANS_INVOICING_RUNNER``.

    Numbering an invoice locks its series row until the outermost transaction
    commits, so invoicing inside the transaction that completes a payment makes
    every payment wait on, and roll back with, invoicing. A runner can move the
    job out of that transaction and out of the request (a task queue after
    commit). Jobs take primary keys so they can be queued, and running one
    again does nothing new.
    """
    runner = getattr(settings, "PLANS_INVOICING_RUNNER", None)
    if runner is None:
        job(*args)
    else:
        import_string(runner)(job, *args)


def create_invoice(order_id, invoice_type):
    Order = AbstractOrder.get_concrete_model()
    Invoice = AbstractInvoice.get_concrete_model()
    order = Order.objects.get(pk=order_id)
    if Invoice.objects.filter(order=order, type=invoice_type).exists():
        return
    Invoice.create(order, invoice_type)


def send_invoice_email(invoice_id):
    Invoice = AbstractInvoice.get_concrete_model()
    Invoice.objects.get(pk=invoice_id).send_invoice_by_email()
