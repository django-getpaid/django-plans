from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from sequences.models import Sequence

from plans.base.models import AbstractBillingInfo, AbstractInvoice, AbstractOrder
from plans.models import PlanPricing

User = get_user_model()
BillingInfo = AbstractBillingInfo.get_concrete_model()
Invoice = AbstractInvoice.get_concrete_model()
Order = AbstractOrder.get_concrete_model()

FIXTURES = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]


def make_order(user):
    plan_pricing = PlanPricing.objects.get(plan=user.userplan.plan, pricing__period=30)
    return Order.objects.create(
        user=user,
        pricing=plan_pricing.pricing,
        amount=100,
        plan=plan_pricing.plan,
    )


@override_settings(PLANS_CREATE_INVOICES_AFTER_COMMIT=True)
class InvoicesAfterCommitTests(TestCase):
    fixtures = FIXTURES

    def setUp(self):
        self.user = User.objects.get(username="test1")
        BillingInfo.objects.get_or_create(user=self.user, defaults={"country": "US"})
        mail.outbox = []

    def test_order_completes_without_touching_the_invoice_series(self):
        with self.captureOnCommitCallbacks() as callbacks:
            order = make_order(self.user)
            self.assertTrue(order.complete_order())

            self.assertFalse(Invoice.objects.filter(order=order).exists())
            self.assertFalse(Sequence.objects.exists())
        self.assertEqual(len(callbacks), 2)

    def test_proforma_invoice_and_their_emails_follow_the_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            order = make_order(self.user)
            order.complete_order()

        self.assertEqual(
            sorted(Invoice.objects.filter(order=order).values_list("type", flat=True)),
            [Invoice.INVOICE_TYPES.INVOICE, Invoice.INVOICE_TYPES.PROFORMA],
        )
        invoice = Invoice.objects.get(order=order, type=Invoice.INVOICE_TYPES.INVOICE)
        self.assertEqual(invoice.full_number, invoice.get_full_number())
        self.assertEqual(
            sum(invoice.full_number in message.body for message in mail.outbox), 1
        )

    @override_settings(PLANS_CREATE_INVOICES_AFTER_COMMIT=False)
    def test_default_numbers_the_invoices_inside_the_order_transaction(self):
        with self.captureOnCommitCallbacks() as callbacks:
            order = make_order(self.user)
            order.complete_order()

            self.assertEqual(Invoice.objects.filter(order=order).count(), 2)
        self.assertEqual(callbacks, [])


@override_settings(PLANS_CREATE_INVOICES_AFTER_COMMIT=True)
class InvoiceFailureAfterCommitTests(TransactionTestCase):
    fixtures = FIXTURES

    def test_failing_invoice_keeps_the_completed_order(self):
        user = User.objects.get(username="test1")
        BillingInfo.objects.get_or_create(user=user, defaults={"country": "US"})
        order = make_order(user)

        with (
            mock.patch.object(Invoice, "create", side_effect=RuntimeError("TEDB down")),
            self.assertLogs("django.db.backends.base", level="ERROR") as logs,
        ):
            with transaction.atomic():
                self.assertTrue(order.complete_order())

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS.COMPLETED)
        self.assertFalse(
            Invoice.objects.filter(
                order=order, type=Invoice.INVOICE_TYPES.INVOICE
            ).exists()
        )
        self.assertIn("TEDB down", "\n".join(logs.output))
