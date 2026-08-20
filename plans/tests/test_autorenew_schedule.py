import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time
from model_bakery import baker

from plans.models import AbstractRecurringUserPlan, RecurringUserPlan
from plans.signals import account_automatic_renewal
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
        """A slot that has already been attempted must not fire again.

        Driven through the task itself: the first run attempts the slot and
        records it, the second run finds the same slot already attempted.
        """
        self.user_plan.expire = timezone.now().date() + datetime.timedelta(days=2)
        self.user_plan.save()

        first = autorenew_account()
        second = autorenew_account()

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)

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


class AutorenewSlotBookkeepingTests(TestCase):
    """One scheduled slot must produce one attempt, at any task cadence.

    ``expire`` is a DateField, so slot bookkeeping is day-granular by nature.
    The replaced implementation inferred "already attempted" from timestamp
    arithmetic that read that date with two different clocks: the renewal
    window coerced it through the *current* time zone while the SQL-side
    guard read it as a naive timestamp in the *connection* time zone. Inside
    the gap between the two readings -- as wide as the UTC offset -- an
    hourly task re-attempted an account whose attempt was already recorded:
    three charges per slot in production, for months. Slots are now
    identified by the local calendar date they open on and compared with
    whole-day arithmetic only.
    """

    def setUp(self):
        self.user = baker.make(
            User, username="spacing_user", email="spacing@example.com"
        )
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

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=-1)],
        TIME_ZONE="Europe/Prague",
    )
    def test_one_slot_is_never_reattempted_across_its_window_tail(self):
        # A slot's window stays open for PLANS_AUTORENEW_MAX_DAYS_AFTER_EXPIRY
        # (30 days by default). One attempt must consume the slot for that
        # whole tail -- not merely for a day or a spacing interval. A
        # duration-based guard passes the hourly tests yet re-attempts here
        # every time the duration elapses, which is how a broken slot guard
        # once charged the same failing card daily for a month.
        self.user_plan.expire = datetime.date(2026, 8, 4)
        self.user_plan.save()

        attempts = self._attempts_at(
            "2026-08-05 10:01:00",
            "2026-08-07 10:01:00",
            "2026-08-14 10:01:00",
            "2026-08-30 10:01:00",
        )

        self.assertEqual(attempts, [1, 0, 0, 0])


class AutorenewConcurrentClaimTests(TestCase):
    """Overlapping task runs must charge each account at most once.

    Two runs can both select the same account before either records its
    attempt; whichever writes first must win and the other must skip. The
    claim is a compare-and-swap on ``last_renewal_attempt``: it only
    records the attempt if the field still holds the value the run selected,
    which is atomic on every backend as a single conditional UPDATE.
    """

    def setUp(self):
        self.user = baker.make(User, username="claimed", email="claimed@example.com")
        self.plan = baker.make("Plan", name="Test Plan")
        self.pricing = baker.make("Pricing", period=30)
        baker.make("PlanPricing", plan=self.plan, pricing=self.pricing, price=10)
        self.user_plan = baker.make(
            "UserPlan",
            user=self.user,
            plan=self.plan,
            expire=datetime.date(2026, 8, 6),
        )
        baker.make(
            RecurringUserPlan,
            user_plan=self.user_plan,
            renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            token_verified=True,
            pricing=self.pricing,
            amount=Decimal(10),
            currency="USD",
        )

    def _snapshot(self):
        # A concurrent run's view of the row: read independently, as its
        # queryset would.
        return RecurringUserPlan.objects.get(pk=self.user_plan.recurring.pk)

    @freeze_time("2026-08-19 22:01:00", auto_tick_seconds=1)
    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=1)])
    def test_receiver_saving_the_recurring_does_not_unrecord_the_claim(self):
        # The production 2026-08-19 regression: the claim updated the row but
        # not the in-memory instance, and plans-payments' renewal receiver
        # ends with a full save of that instance (create_renew_order stores
        # the recalculated tax) -- writing the pre-claim timestamp back. The
        # attempt was un-recorded and every later task run retried the same
        # account (hourly card-banging).
        self.user_plan.expire = datetime.date(2026, 8, 20)
        self.user_plan.save()
        stale = timezone.now() - datetime.timedelta(days=30)
        RecurringUserPlan.objects.filter(pk=self.user_plan.recurring.pk).update(
            last_renewal_attempt=stale
        )

        renewed = []

        def renew_receiver(sender, user, *args, **kwargs):
            renewed.append(user.pk)
            user.userplan.recurring.tax = Decimal(21)
            user.userplan.recurring.save()

        account_automatic_renewal.connect(renew_receiver)
        try:
            autorenew_account()
            autorenew_account()  # the next cron tick inside the same slot
        finally:
            account_automatic_renewal.disconnect(renew_receiver)

        self.assertEqual(
            len(renewed),
            1,
            "the second run inside the slot re-attempted: the receiver's save "
            "clobbered the claimed last_renewal_attempt back to the stale value",
        )
        recurring = RecurringUserPlan.objects.get(pk=self.user_plan.recurring.pk)
        self.assertGreater(recurring.last_renewal_attempt, stale)

    def test_stale_snapshot_loses_the_claim(self):
        from plans.tasks import _claim_renewal_attempt

        first_run = self._snapshot()
        second_run = self._snapshot()

        self.assertTrue(_claim_renewal_attempt(first_run))
        self.assertFalse(_claim_renewal_attempt(second_run))

    def test_claim_also_races_correctly_on_a_later_slot(self):
        from plans.tasks import _claim_renewal_attempt

        previous = timezone.now() - datetime.timedelta(days=2)
        RecurringUserPlan.objects.filter(pk=self.user_plan.recurring.pk).update(
            last_renewal_attempt=previous
        )

        first_run = self._snapshot()
        second_run = self._snapshot()

        self.assertTrue(_claim_renewal_attempt(first_run))
        self.assertFalse(_claim_renewal_attempt(second_run))

    @override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=1)])
    @freeze_time("2026-08-05 12:00:00")
    def test_lost_claim_skips_the_signal(self):
        signals = []

        def receiver(sender, user, **kwargs):
            signals.append(user)

        account_automatic_renewal.connect(receiver)
        self.addCleanup(account_automatic_renewal.disconnect, receiver)

        # Simulate the overlapping run winning between this run's selection
        # and its claim: the selection sees the account, the claim must not.
        from plans import tasks as tasks_module

        original_claim = tasks_module._claim_renewal_attempt

        def racing_claim(recurring):
            RecurringUserPlan.objects.filter(pk=recurring.pk).update(
                last_renewal_attempt=timezone.now()
            )
            return original_claim(recurring)

        tasks_module._claim_renewal_attempt = racing_claim
        self.addCleanup(setattr, tasks_module, "_claim_renewal_attempt", original_claim)

        attempted = autorenew_account()

        self.assertEqual(signals, [])
        self.assertEqual(attempted, [])
