import datetime
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from model_bakery import baker


class ManagementCommandTests(TestCase):
    def test_command_output(self):
        out = StringIO()
        call_command("autorenew_accounts", stdout=out)
        self.assertEqual(out.getvalue(), "Starting renewal\nNo accounts autorenewed\n")

    def test_renewal(self):
        self.user = baker.make("User", username="testuser")
        plan_pricing = baker.make(
            "PlanPricing", plan=baker.make("Plan", name="Foo plan")
        )
        baker.make(
            "UserPlan",
            user=self.user,
            plan=plan_pricing.plan,
            recurring__payment_provider="internal-payment-recurring",
            recurring__amount=Decimal(123),
            recurring__pricing=plan_pricing.pricing,
            recurring__currency="USD",
            recurring__has_automatic_renewal=True,
            recurring__token_verified=True,
            expire=datetime.date(2020, 1, 2),
        )
        out = StringIO()
        call_command("autorenew_accounts", stdout=out)
        self.assertEqual(
            out.getvalue().strip(),
            "Starting renewal\nAccounts submitted to renewal:\n\tinternal-payment-recurring\t\ttestuser",
        )

    def test_renewal_providers(self):
        self.user = baker.make("User", username="testuser")
        plan_pricing = baker.make(
            "PlanPricing", plan=baker.make("Plan", name="Foo plan")
        )
        baker.make(
            "UserPlan",
            user=self.user,
            plan=plan_pricing.plan,
            recurring__payment_provider="internal-payment-recurring",
            recurring__amount=Decimal(123),
            recurring__pricing=plan_pricing.pricing,
            recurring__currency="USD",
            recurring__has_automatic_renewal=True,
            recurring__token_verified=True,
            expire=datetime.date(2020, 1, 2),
        )
        out = StringIO()
        call_command("autorenew_accounts", providers="foo", stdout=out)
        self.assertEqual(out.getvalue(), "Starting renewal\nNo accounts autorenewed\n")
