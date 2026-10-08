from datetime import date, datetime, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time
from model_bakery import baker

SCHEDULE = [timedelta(days=3), timedelta(days=1), timedelta(days=-2)]
EXPIRE = date(2026, 10, 20)


def at_noon(day):
    return timezone.make_aware(
        datetime.combine(day, datetime.min.time()).replace(hour=12)
    )


@override_settings(PLANS_AUTORENEW_SCHEDULE=SCHEDULE)
class PlanAutorenewAtScheduleTests(TestCase):
    def user_plan(self, last_attempt_day=None):
        user_plan = baker.make("UserPlan", expire=EXPIRE)
        baker.make(
            "RecurringUserPlan",
            user_plan=user_plan,
            last_renewal_attempt=last_attempt_day and at_noon(last_attempt_day),
        )
        user_plan.refresh_from_db()
        return user_plan

    @freeze_time("2026-10-10 12:00")
    def test_first_slot_before_expiry(self):
        self.assertEqual(self.user_plan().plan_autorenew_at(), date(2026, 10, 17))

    @freeze_time("2026-10-10 12:00")
    def test_without_a_recurring_plan(self):
        user_plan = baker.make("UserPlan", expire=EXPIRE)
        self.assertEqual(user_plan.plan_autorenew_at(), date(2026, 10, 17))

    @freeze_time("2026-10-18 12:00")
    def test_next_slot_after_an_attempt(self):
        self.assertEqual(
            self.user_plan(last_attempt_day=date(2026, 10, 17)).plan_autorenew_at(),
            date(2026, 10, 19),
        )

    @freeze_time("2026-10-21 12:00")
    def test_retry_after_expiry(self):
        self.assertEqual(
            self.user_plan(last_attempt_day=date(2026, 10, 19)).plan_autorenew_at(),
            date(2026, 10, 22),
        )

    @freeze_time("2026-10-24 12:00")
    def test_a_missed_slot_is_taken_today(self):
        self.assertEqual(
            self.user_plan(last_attempt_day=date(2026, 10, 19)).plan_autorenew_at(),
            date(2026, 10, 24),
        )

    @freeze_time("2026-10-23 12:00")
    def test_none_when_every_slot_fired(self):
        self.assertIsNone(
            self.user_plan(last_attempt_day=date(2026, 10, 22)).plan_autorenew_at()
        )

    @freeze_time("2026-12-01 12:00")
    @override_settings(PLANS_AUTORENEW_MAX_DAYS_AFTER_EXPIRY=timedelta(days=30))
    def test_none_once_the_renewal_window_closed(self):
        self.assertIsNone(self.user_plan().plan_autorenew_at())

    @freeze_time("2026-10-10 12:00")
    @override_settings(PLANS_AUTORENEW_SCHEDULE=[timedelta(hours=12)])
    def test_a_partial_day_offset_opens_the_day_before(self):
        self.assertEqual(self.user_plan().plan_autorenew_at(), date(2026, 10, 19))
