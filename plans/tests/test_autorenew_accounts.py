import datetime
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from model_bakery import baker

from plans.models import AbstractRecurringUserPlan


class ManagementCommandTests(TestCase):
    def test_command_output(self):
        out = StringIO()
        with self.assertWarns(DeprecationWarning):
            call_command("autorenew_accounts", stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Starting renewal\n"
            "Started automatic account renewal\n"
            "0 accounts to be renewed.\n"
            "No accounts autorenewed\n",
        )

    def test_renewal(self):
        _make_user(
            userplan__expire=datetime.date(2020, 1, 2),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            userplan__recurring__token_verified=True,
        )
        out = StringIO()
        with self.assertWarns(DeprecationWarning):
            call_command("autorenew_accounts", stdout=out)
        self.assertEqual(
            out.getvalue().strip(),
            "Starting renewal\n"
            "Started automatic account renewal\n"
            "1 accounts to be renewed.\n"
            "1 accounts submitted to renewal:\n"
            "\tinternal-payment-recurring                                            "
            "testuser                                2020-01-02\tTrue",
        )

    def test_renewal_triggered_by_user(self):
        _make_user(
            userplan__expire=datetime.date(2020, 1, 2),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.USER,
            userplan__recurring__token_verified=True,
        )
        out = StringIO()
        with self.assertWarns(DeprecationWarning):
            call_command("autorenew_accounts", stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Starting renewal\n"
            "Started automatic account renewal\n"
            "0 accounts to be renewed.\n"
            "No accounts autorenewed\n",
        )

    def test_renewal_triggered_by_other(self):
        _make_user(
            userplan__expire=datetime.date(2020, 1, 2),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.OTHER,
            userplan__recurring__token_verified=True,
        )
        out = StringIO()
        with self.assertWarns(DeprecationWarning):
            call_command("autorenew_accounts", stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Starting renewal\n"
            "Started automatic account renewal\n"
            "0 accounts to be renewed.\n"
            "No accounts autorenewed\n",
        )

    def test_renewal_providers(self):
        _make_user(
            userplan__expire=datetime.date(2020, 1, 2),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            userplan__recurring__payment_provider="internal-payment-recurring",
            userplan__recurring__token_verified=True,
        )
        out = StringIO()
        with self.assertWarns(DeprecationWarning):
            call_command("autorenew_accounts", providers="foo", stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Starting renewal\n"
            "Started automatic account renewal\n"
            "0 accounts to be renewed.\n"
            "No accounts autorenewed\n",
        )

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=3)])
    def test_renewal_with_date_parameter(self):
        """Test that --date parameter allows simulating renewals for specific dates."""
        # Plan expires on 2023-01-15
        _make_user(
            userplan__expire=datetime.date(2023, 1, 15),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            userplan__recurring__token_verified=True,
        )

        # Simulate 2023-01-13 (2 days before expiry)
        # Schedule is 3 days, so should renew
        out = StringIO()
        call_command("autorenew_accounts", date="2023-01-13", stdout=out)
        output = out.getvalue()

        self.assertIn("Starting renewal", output)
        self.assertIn("Simulating renewals as if today were: 2023-01-13", output)
        self.assertIn("1 accounts to be renewed", output)
        self.assertIn("1 accounts submitted to renewal", output)

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=3)])
    def test_renewal_with_date_parameter_should_not_renew(self):
        """Test that --date parameter correctly excludes plans outside the window."""
        # Plan expires on 2023-01-15
        _make_user(
            userplan__expire=datetime.date(2023, 1, 15),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            userplan__recurring__token_verified=True,
        )

        # Simulate 2023-01-10 (5 days before expiry)
        # Schedule is 3 days, so should NOT renew
        out = StringIO()
        call_command("autorenew_accounts", date="2023-01-10", stdout=out)
        output = out.getvalue()

        self.assertIn("Starting renewal", output)
        self.assertIn("Simulating renewals as if today were: 2023-01-10", output)
        self.assertIn("0 accounts to be renewed", output)
        self.assertIn("No accounts autorenewed", output)

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=3)])
    def test_renewal_with_date_parameter_dry_run(self):
        """Test that --date parameter works with --dry-run."""
        # Plan expires on 2023-01-15
        _make_user(
            userplan__expire=datetime.date(2023, 1, 15),
            userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            userplan__recurring__token_verified=True,
        )

        # Simulate 2023-01-13 with dry-run
        out = StringIO()
        call_command("autorenew_accounts", date="2023-01-13", dry_run=True, stdout=out)
        output = out.getvalue()

        self.assertIn("DRY RUN active", output)
        self.assertIn("Simulating renewals as if today were: 2023-01-13", output)
        self.assertIn("1 accounts would be submitted to renewal", output)


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
