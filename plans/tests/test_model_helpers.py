from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
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
