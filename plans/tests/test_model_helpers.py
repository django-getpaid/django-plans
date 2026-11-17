from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.utils import translation
from django.utils.timezone import make_aware
from model_bakery import baker

from plans.base.models import (
    AbstractBillingInfo,
    AbstractInvoice,
    AbstractOrder,
    AbstractPlan,
    AbstractPlanPricing,
    AbstractUserPlan,
)
from plans.signals import user_language

User = get_user_model()
BillingInfo = AbstractBillingInfo.get_concrete_model()
Invoice = AbstractInvoice.get_concrete_model()
Order = AbstractOrder.get_concrete_model()
Plan = AbstractPlan.get_concrete_model()
PlanPricing = AbstractPlanPricing.get_concrete_model()
UserPlan = AbstractUserPlan.get_concrete_model()


def speaks_portuguese(sender, user, return_value, **kwargs):
    return_value["language"] = "pt-br"


class UserLanguageTestCase(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.customer = baker.make(User, username="customer", email="c@example.com")
        self.plan_pricing = PlanPricing.objects.get(
            plan__name="Standard", pricing__period=30
        )
        user_language.connect(speaks_portuguese)
        self.addCleanup(user_language.disconnect, speaks_portuguese)

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

    def _billing_info(self):
        baker.make(
            BillingInfo,
            user=self.customer,
            name="Customer Ltd",
            country="US",
            tax_number="",
        )


class InvoiceLanguageTests(UserLanguageTestCase):
    def test_no_invoice_without_billing_info_and_the_language_is_restored(self):
        self.assertIsNone(Invoice.create(self._order(), Invoice.INVOICE_TYPES.INVOICE))

        self.assertEqual(translation.get_language(), "en")

    def test_invoice_is_created_in_the_users_language_and_the_language_restored(self):
        self._billing_info()

        invoice = Invoice.create(self._order(), Invoice.INVOICE_TYPES.INVOICE)

        self.assertEqual(invoice.buyer_name, "Customer Ltd")
        self.assertEqual(translation.get_language(), "en")

    def test_invoice_e_mail_goes_out_in_the_users_language(self):
        self._billing_info()
        invoice = Invoice.create(self._order(), Invoice.INVOICE_TYPES.INVOICE)
        mail.outbox = []

        invoice.send_invoice_by_email()

        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(mail.outbox[0].subject.startswith("Pedido "))
        self.assertEqual(translation.get_language(), "en")

    def test_invoice_e_mail_is_not_sent_for_a_disabled_invoice_type(self):
        self._billing_info()
        invoice = Invoice.create(self._order(), Invoice.INVOICE_TYPES.INVOICE)
        mail.outbox = []

        with override_settings(
            PLANS_SEND_EMAILS_DISABLED_INVOICE_TYPES=[Invoice.INVOICE_TYPES.INVOICE]
        ):
            invoice.send_invoice_by_email()

        self.assertEqual(mail.outbox, [])


class OrderHelperTests(UserLanguageTestCase):
    def test_flat_name_replaces_the_plan_name(self):
        self.assertEqual(
            self._order(flat_name="Legacy subscription").name, "Legacy subscription"
        )

    def test_invoices_are_listed_by_type(self):
        """Saving an order with billing info issues its proforma right away."""
        self._billing_info()
        order = self._order()
        proforma = Invoice.proforma.get(order=order)
        invoice = Invoice.create(order, Invoice.INVOICE_TYPES.INVOICE)
        duplicate = Invoice.create(order, Invoice.INVOICE_TYPES.DUPLICATE)
        credit_note = invoice.cancel_invoice()

        self.assertEqual(list(order.get_invoices()), [invoice])
        self.assertEqual(list(order.get_invoices_proforma()), [proforma])
        self.assertEqual(list(Invoice.duplicates.filter(order=order)), [duplicate])
        self.assertEqual(list(order.get_credit_notes()), [credit_note])

    def test_plan_pricing_of_the_order(self):
        self.assertEqual(self._order().get_plan_pricing(), self.plan_pricing)


class UserPlanHelperTests(UserLanguageTestCase):
    def test_current_plan_of_an_active_account(self):
        UserPlan.objects.filter(user=self.customer).update(
            plan=self.plan_pricing.plan, expire=None
        )

        self.assertEqual(
            UserPlan.objects.get(user=self.customer).get_current_plan(),
            self.plan_pricing.plan,
        )

    def test_reducing_without_a_pricing_keeps_the_expiry(self):
        user_plan = UserPlan.objects.get(user=self.customer)
        user_plan.expire = date(2024, 2, 14)

        self.assertEqual(user_plan.get_plan_reduced_until(None), date(2024, 2, 14))


class InvoiceNumberingTests(UserLanguageTestCase):
    @override_settings(PLANS_INVOICE_COUNTER_RESET="weekly")
    def test_unknown_counter_reset_is_a_configuration_error(self):
        self._billing_info()

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "PLANS_INVOICE_COUNTER_RESET can be set only to these values",
        ):
            Invoice.create(self._order(), Invoice.INVOICE_TYPES.INVOICE)
