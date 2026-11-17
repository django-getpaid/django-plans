from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.timezone import make_aware
from model_bakery import baker

from plans.base.models import (
    AbstractBillingInfo,
    AbstractInvoice,
    AbstractOrder,
    AbstractPlanPricing,
    AbstractUserPlan,
)

User = get_user_model()
BillingInfo = AbstractBillingInfo.get_concrete_model()
Invoice = AbstractInvoice.get_concrete_model()
Order = AbstractOrder.get_concrete_model()
PlanPricing = AbstractPlanPricing.get_concrete_model()
UserPlan = AbstractUserPlan.get_concrete_model()


class InvoiceOrderGuardsTestCase(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.customer = baker.make(User, username="customer")
        baker.make(BillingInfo, user=self.customer, country="US", tax_number="")
        self.plan_pricing = PlanPricing.objects.get(
            plan__name="Standard", pricing__period=30
        )

    def _order(self, **kwargs):
        fields = dict(
            user=self.customer,
            plan=self.plan_pricing.plan,
            pricing=self.plan_pricing.pricing,
            amount=Decimal("100.00"),
            tax=Decimal("23.00"),
            currency="EUR",
            completed=make_aware(datetime(2024, 1, 15, 12)),
        )
        fields.update(kwargs)
        return Order.objects.create(**fields)


class InvoiceCancellationGuardsTests(InvoiceOrderGuardsTestCase):
    def test_credit_note_cannot_be_cancelled(self):
        credit_note = Invoice.create(
            self._order(), Invoice.INVOICE_TYPES.INVOICE
        ).cancel_invoice()

        with self.assertRaisesMessage(
            ValidationError, "Only invoices can be cancelled."
        ):
            credit_note.cancel_invoice()

        self.assertFalse(Invoice.objects.filter(credit_note_for=credit_note).exists())

    def test_credit_note_cannot_get_a_partial_credit_note(self):
        credit_note = Invoice.create(
            self._order(), Invoice.INVOICE_TYPES.INVOICE
        ).cancel_invoice()

        with self.assertRaisesMessage(
            ValidationError, "Only invoices can have partial credit notes."
        ):
            credit_note.create_partial_credit_note(Decimal("10"), Decimal("2.30"))

        self.assertFalse(Invoice.objects.filter(credit_note_for=credit_note).exists())


class ReturnOrderGuardsTests(InvoiceOrderGuardsTestCase):
    def test_order_without_its_extension_window_is_not_returned(self):
        """A completed order with no recorded extension can't be rewound safely.

        Reducing the account by ``pricing.period`` without knowing what the
        order extended could take days the customer paid for elsewhere.
        """
        order = self._order(
            status=Order.STATUS.COMPLETED,
            plan_extended_from=None,
            plan_extended_until=None,
        )
        invoice = Invoice.create(order, Invoice.INVOICE_TYPES.INVOICE)
        UserPlan.objects.filter(user=self.customer).update(
            plan=self.plan_pricing.plan, expire=date(2024, 2, 14)
        )

        with self.assertRaisesMessage(ValueError, "Invalid order state"):
            order.return_order()

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS.COMPLETED)
        self.assertEqual(
            UserPlan.objects.get(user=self.customer).expire, date(2024, 2, 14)
        )
        self.assertFalse(Invoice.credit_notes.filter(credit_note_for=invoice).exists())

    def test_new_order_cannot_be_returned(self):
        order = self._order(status=Order.STATUS.NEW, completed=None)

        with self.assertRaisesMessage(
            ValueError, "Cannot return order with status other than COMPLETED"
        ):
            order.return_order()

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS.NEW)
