import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from freezegun import freeze_time
from model_bakery import baker

from plans.base.models import AbstractRecurringUserPlan
from plans.models import RecurringUserPlan
from plans.tasks import expire_account

User = get_user_model()


@override_settings(TIME_ZONE="America/New_York")
@freeze_time("2026-08-05 02:00:00")  # UTC is Aug 5; New York is still Aug 4, 22:00
class BusinessDatesUseTheActiveTimezoneTests(TestCase):
    """Business-date arithmetic must use the active time zone's date.

    ``timezone.now().date()`` is the UTC date; for any time zone behind UTC
    there is a nightly window in which UTC has moved to the next day while
    the active time zone has not, and every "is it expired yet?" style
    calculation flips a day early (issue #236 -- the mirror image of the
    autorenew slot bug, which hit time zones ahead of UTC).
    """

    def setUp(self):
        self.user = baker.make(User, username="tz_user", email="tz@example.com")
        self.plan = baker.make("Plan", name="Test Plan")
        self.pricing = baker.make("Pricing", period=30)
        baker.make("PlanPricing", plan=self.plan, pricing=self.pricing, price=10)
        # Expires "today" in New York -- still valid for two more local hours.
        self.user_plan = baker.make(
            "UserPlan",
            user=self.user,
            plan=self.plan,
            expire=datetime.date(2026, 8, 4),
            active=True,
        )

    def test_plan_expiring_today_is_not_expired_yet(self):
        self.assertFalse(self.user_plan.is_expired())

    def test_days_left_counts_from_the_local_date(self):
        self.assertEqual(self.user_plan.days_left(), 0)

    def test_expire_account_does_not_expire_a_day_early(self):
        baker.make(
            RecurringUserPlan,
            user_plan=self.user_plan,
            renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            token_verified=True,
            pricing=self.pricing,
            amount=Decimal(10),
            currency="USD",
        )

        expire_account()

        self.user_plan.refresh_from_db()
        self.assertTrue(self.user_plan.active)
