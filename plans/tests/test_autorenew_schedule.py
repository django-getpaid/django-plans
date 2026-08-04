import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time
from model_bakery import baker

from plans.models import AbstractRecurringUserPlan, RecurringUserPlan
from plans.tasks import autorenew_account

User = get_user_model()


class AutorenewSchedulerTests(TestCase):
    def setUp(self):
        self.user = baker.make(User, username="test_user", email="test@example.com")
        self.plan = baker.make("Plan", name="Test Plan")
        self.pricing = baker.make("Pricing", period=30)
        baker.make("PlanPricing", plan=self.plan, pricing=self.pricing, price=10)
        self.user_plan = baker.make(
            "UserPlan",
            user=self.user,
            plan=self.plan,
        )
        # Baker's direct creation of related one-to-one objects can be tricky,
        # so we create the RecurringUserPlan explicitly.
        baker.make(
            RecurringUserPlan,
            user_plan=self.user_plan,
            renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            token_verified=True,
            pricing=self.pricing,
            amount=Decimal(10),
            currency="USD",
        )

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=3)])
    @freeze_time("2023-01-01 12:00:00")
    def test_autorenew_schedule_before_expiry_should_renew(self):
        """Plan expires in 2 days, schedule is 3 days, should renew."""
        self.user_plan.expire = timezone.now().date() + datetime.timedelta(days=2)
        self.user_plan.save()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 1)
        self.assertEqual(renewed[0], self.user)

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=3)])
    @freeze_time("2023-01-01 12:00:00")
    def test_autorenew_schedule_before_expiry_should_not_renew(self):
        """Plan expires in 4 days, schedule is 3 days, should NOT renew."""
        self.user_plan.expire = timezone.now().date() + datetime.timedelta(days=4)
        self.user_plan.save()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 0)

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=-2)])
    @freeze_time("2023-01-10 12:00:00")
    def test_autorenew_schedule_after_expiry_should_renew(self):
        """Plan expired 3 days ago, schedule is -2 days, should renew."""
        self.user_plan.expire = timezone.now().date() - datetime.timedelta(
            days=3
        )  # expired 2023-01-07
        self.user_plan.save()
        self.user_plan.expire_account()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 1)
        self.assertEqual(renewed[0], self.user)

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=-2)])
    @freeze_time("2023-01-10 12:00:00")
    def test_autorenew_schedule_after_expiry_should_not_renew(self):
        """Plan expired 1 day ago, schedule is -2 days, should NOT renew."""
        self.user_plan.expire = timezone.now().date() - datetime.timedelta(
            days=1
        )  # expired 2023-01-09
        self.user_plan.save()
        self.user_plan.expire_account()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 0)

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=3)])
    @freeze_time("2023-01-01 12:00:00")
    def test_autorenew_schedule_should_not_renew_recently_attempted(self):
        """Plan should not renew if a renewal was attempted recently."""
        self.user_plan.expire = timezone.now().date() + datetime.timedelta(days=2)
        self.user_plan.recurring.last_renewal_attempt = timezone.now()
        self.user_plan.save()
        self.user_plan.recurring.save()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 0)

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=3)])
    @freeze_time("2023-01-10 12:00:00")
    def test_autorenew_schedule_should_renew_attempted_long_ago(self):
        """Plan should renew if a renewal was attempted before the renewal window."""
        self.user_plan.expire = timezone.now().date() + datetime.timedelta(
            days=2
        )  # 2023-01-12
        # expire - schedule = 2023-01-09
        self.user_plan.recurring.last_renewal_attempt = timezone.make_aware(
            datetime.datetime(2023, 1, 8, 11, 59, 59)
        )
        self.user_plan.save()
        self.user_plan.recurring.save()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 1)
        self.assertEqual(renewed[0], self.user)

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[
            datetime.timedelta(days=1),
            datetime.timedelta(days=5),
        ]
    )
    @freeze_time("2023-01-01 12:00:00")
    def test_autorenew_multiple_schedules_should_renew(self):
        """Plan should renew if one of multiple schedules is met."""
        self.user_plan.expire = timezone.now().date() + datetime.timedelta(days=4)
        self.user_plan.save()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 1)
        self.assertEqual(renewed[0], self.user)

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[
            datetime.timedelta(days=1),
            datetime.timedelta(days=2),
        ]
    )
    @freeze_time("2023-01-01 12:00:00")
    def test_autorenew_multiple_schedules_should_not_renew(self):
        """Plan should not renew if no multiple schedules are met."""
        self.user_plan.expire = timezone.now().date() + datetime.timedelta(days=4)
        self.user_plan.save()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 0)

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[
            datetime.timedelta(days=1),
            datetime.timedelta(days=-1),
        ]
    )
    @freeze_time("2023-01-10 12:00:00")
    def test_autorenew_mixed_schedules_after_expiry(self):
        """Plan should renew with mixed (positive/negative) schedules after expiry."""
        self.user_plan.expire = timezone.now().date() - datetime.timedelta(days=1)
        self.user_plan.save()
        self.user_plan.expire_account()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 1)
        self.assertEqual(renewed[0], self.user)

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=3)])
    @freeze_time("2023-01-01 12:00:00", auto_tick_seconds=1)
    def test_autorenew_schedule_does_not_renew_twice(self):
        """A plan should not be renewed twice for the same schedule."""
        self.user_plan.expire = timezone.now().date() + datetime.timedelta(days=2)
        self.user_plan.save()

        # First run, should renew
        renewed_first = autorenew_account()
        self.assertEqual(len(renewed_first), 1)
        self.assertEqual(renewed_first[0], self.user)

        # Second run, should NOT renew
        renewed_second = autorenew_account()
        self.assertEqual(len(renewed_second), 0)

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=-2)],
        PLANS_AUTORENEW_MAX_DAYS_AFTER_EXPIRY=datetime.timedelta(days=30),
    )
    @freeze_time("2023-01-31 00:00:01")
    def test_autorenew_respects_max_days_after_expiry(self):
        """
        Plan expired exactly on the edge of the max_renew_after window.
        It should be renewed. This test would fail without the `.date()`
        conversion in the task.
        """
        self.user_plan.expire = datetime.date(2022, 12, 30)
        self.user_plan.save()
        self.user_plan.expire_account()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 1)
        self.assertEqual(renewed[0], self.user)

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=-2)],
        PLANS_AUTORENEW_MAX_DAYS_AFTER_EXPIRY=datetime.timedelta(days=30),
    )
    @freeze_time("2023-01-31 12:00:00")
    def test_autorenew_respects_max_days_after_expiry_should_not_renew(self):
        """
        Plan expired one day before the max_renew_after window.
        It should NOT be renewed.
        """
        # renewal window starts at 2022-12-30
        self.user_plan.expire = datetime.date(2022, 12, 29)
        self.user_plan.save()
        self.user_plan.expire_account()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 0)

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=1)],
        PLANS_AUTORENEW_MAX_DAYS_AFTER_EXPIRY=datetime.timedelta(days=5),
    )
    @freeze_time("2025-06-07 12:10:30")
    def test_autorenew_date_comparison_is_correct(self):
        """
        Tests that comparing a DateField (expire) with a datetime object
        works correctly by using .date() to truncate the time part.
        Without .date(), this test should fail.
        """
        self.user_plan.expire = datetime.date(2025, 6, 7)
        self.user_plan.save()
        self.user_plan.expire_account()

        renewed = autorenew_account()
        self.assertEqual(len(renewed), 1)
        self.assertEqual(renewed[0], self.user)


class AutorenewAttemptSpacingTests(TestCase):
    """One scheduled slot must produce one attempt, at any task cadence.

    The window test (``expire <= now + offset``) coerces the datetime to a
    date in the *current time zone*; the guard (``last_renewal_attempt <
    expire - offset``) is computed in SQL, where ``date - interval`` yields a
    naive timestamp read in the *connection* time zone. Between the two
    readings of the same date lies a gap as wide as the UTC offset, and a
    task run inside it re-qualifies the user even though the previous attempt
    was recorded. Under an hourly scheduler this charged failing cards three
    times per slot in production (offset + 1 attempts), for months.
    """

    def setUp(self):
        self.user = baker.make(User, username="spacing_user", email="spacing@example.com")
        self.plan = baker.make("Plan", name="Test Plan")
        self.pricing = baker.make("Pricing", period=30)
        baker.make("PlanPricing", plan=self.plan, pricing=self.pricing, price=10)
        self.user_plan = baker.make("UserPlan", user=self.user, plan=self.plan)
        baker.make(
            RecurringUserPlan,
            user_plan=self.user_plan,
            renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            token_verified=True,
            pricing=self.pricing,
            amount=Decimal(10),
            currency="USD",
        )

    def _attempts_at(self, *instants):
        attempts = []
        for instant in instants:
            with freeze_time(instant):
                attempts.append(len(autorenew_account()))
        return attempts

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=1, hours=3)],
        TIME_ZONE="Europe/Prague",
    )
    def test_hourly_runs_in_the_timezone_gap_attempt_only_once(self):
        # The production trace, verbatim: plan expires 2026-08-04 (CEST,
        # UTC+2). The window opens with the Prague date at 19:01 UTC; the SQL
        # guard boundary sits at 21:00 UTC. Hourly runs re-attempted at
        # 20:01 and 21:01 before the guard finally closed.
        self.user_plan.expire = datetime.date(2026, 8, 4)
        self.user_plan.save()

        attempts = self._attempts_at(
            "2026-08-02 19:01:00",
            "2026-08-02 20:01:00",
            "2026-08-02 21:01:00",
            "2026-08-02 22:01:00",
        )

        self.assertEqual(sum(attempts), 1, attempts)

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[
            datetime.timedelta(days=1, hours=3),
            datetime.timedelta(0),
        ],
        TIME_ZONE="Europe/Prague",
    )
    def test_the_next_scheduled_slot_still_fires(self):
        # The spacing must close the gap, not the schedule: after the
        # 1d3h-slot attempt, the on-expiry slot a day later must still run.
        self.user_plan.expire = datetime.date(2026, 8, 4)
        self.user_plan.save()

        first_day = self._attempts_at(
            "2026-08-02 19:01:00",
            "2026-08-02 20:01:00",
        )
        next_day = self._attempts_at(
            "2026-08-03 22:01:00",
            "2026-08-03 23:01:00",
        )

        self.assertEqual(sum(first_day), 1, first_day)
        self.assertEqual(sum(next_day), 1, next_day)
