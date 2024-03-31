import datetime
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from model_bakery import baker

from plans.models import AbstractRecurringUserPlan


class ManagementCommandTests(TestCase):
    def test_command_output(self):
        out = StringIO()
        call_command("autorenew_accounts", stdout=out)
        self.assertEqual(out.getvalue(), "Starting renewal\nNo accounts autorenewed\n")

    def test_renewal(self):
        _make_user(
            userplan__expire=datetime.date(2020, 1, 2),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            userplan__recurring__token_verified=True,
        )
        out = StringIO()
        call_command("autorenew_accounts", stdout=out)
        self.assertEqual(
            out.getvalue().strip(),
            "Starting renewal\nAccounts submitted to renewal:\n\tinternal-payment-recurring\t\ttestuser",
        )

    def test_renewal_triggered_by_user(self):
        _make_user(
            userplan__expire=datetime.date(2020, 1, 2),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.USER,
            userplan__recurring__token_verified=True,
        )
        out = StringIO()
        call_command("autorenew_accounts", stdout=out)
        self.assertEqual(out.getvalue(), "Starting renewal\nNo accounts autorenewed\n")

    def test_renewal_triggered_by_other(self):
        _make_user(
            userplan__expire=datetime.date(2020, 1, 2),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.OTHER,
            userplan__recurring__token_verified=True,
        )
        out = StringIO()
        call_command("autorenew_accounts", stdout=out)
        self.assertEqual(out.getvalue(), "Starting renewal\nNo accounts autorenewed\n")

    def test_renewal_providers(self):
        _make_user(
            userplan__expire=datetime.date(2020, 1, 2),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            userplan__recurring__payment_provider="internal-payment-recurring",
            userplan__recurring__token_verified=True,
        )
        out = StringIO()
        call_command("autorenew_accounts", providers="foo", stdout=out)
        self.assertEqual(out.getvalue(), "Starting renewal\nNo accounts autorenewed\n")


def _make_user(
    userplan__expire,
    userplan__recurring__renewal_triggered_by,
    userplan__recurring__token_verified,
    userplan__recurring__payment_provider="internal-payment-recurring",
):
    user = baker.make("User", username="testuser")
    plan_pricing = baker.make("PlanPricing", plan=baker.make("Plan", name="Foo plan"))
    baker.make(
        "UserPlan",
        user=user,
        plan=plan_pricing.plan,
        recurring__payment_provider=userplan__recurring__payment_provider,
        recurring__amount=Decimal(123),
        recurring__pricing=plan_pricing.pricing,
        recurring__currency="USD",
        recurring__renewal_triggered_by=userplan__recurring__renewal_triggered_by,
        recurring__token_verified=userplan__recurring__token_verified,
        expire=userplan__expire,
    )
