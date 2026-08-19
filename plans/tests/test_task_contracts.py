import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time
from model_bakery import baker

from plans.base.models import AbstractRecurringUserPlan
from plans.models import RecurringUserPlan
from plans.signals import account_automatic_renewal
from plans.tasks import autorenew_account, expire_account

User = get_user_model()


def _renewable_user(username, expire):
    user = baker.make(User, username=username, email=f"{username}@example.com")
    plan = baker.make("Plan", name=f"Plan {username}")
    pricing = baker.make("Pricing", period=30)
    baker.make("PlanPricing", plan=plan, pricing=pricing, price=10)
    user_plan = baker.make("UserPlan", user=user, plan=plan, expire=expire, active=True)
    baker.make(
        RecurringUserPlan,
        user_plan=user_plan,
        renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
        token_verified=True,
        pricing=pricing,
        amount=Decimal(10),
        currency="USD",
    )
    return user


@override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=1)])
@freeze_time("2026-08-05 12:00:00")
class AutorenewFailureIsolationTests(TestCase):
    """One account's failing charge must not decide the whole batch's fate.

    In production the renewal signal talks to a payment provider; a provider
    exception for one customer is routine. The batch semantics around it are
    load-bearing and were untested: with ``catch_exceptions`` the remaining
    accounts must still renew and admins must hear about the failure; without
    it (the default) the failure must stay loud.
    """

    def setUp(self):
        expires_tomorrow = datetime.date(2026, 8, 6)
        self.failing = _renewable_user("failing", expires_tomorrow)
        self.healthy = _renewable_user("healthy", expires_tomorrow)
        self.renewed = []

        def receiver(sender, user, **kwargs):
            if user == self.failing:
                raise RuntimeError("provider declined in a novel way")
            self.renewed.append(user)

        account_automatic_renewal.connect(receiver)
        self.addCleanup(account_automatic_renewal.disconnect, receiver)

    @override_settings(ADMINS=[("Admin", "admin@example.com")])
    def test_catch_exceptions_isolates_the_failure(self):
        attempted = autorenew_account(catch_exceptions=True)

        self.assertIn(self.healthy, self.renewed)
        self.assertIn(self.failing, attempted)
        admin_mail = [m for m in mail.outbox if "Failed to renew" in m.subject]
        self.assertEqual(len(admin_mail), 1)
        self.assertIn(str(self.failing.pk), admin_mail[0].body)

    def test_catch_exceptions_still_records_the_failed_attempt(self):
        # Deliberate contract: a crashed charge consumes the slot too --
        # otherwise a frequently scheduled task hammers the failing card
        # until the slot closes.
        autorenew_account(catch_exceptions=True)

        self.failing.userplan.recurring.refresh_from_db()
        self.assertIsNotNone(self.failing.userplan.recurring.last_renewal_attempt)

    def test_default_lets_the_failure_propagate(self):
        with self.assertRaises(RuntimeError):
            autorenew_account()


@override_settings(PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=1)])
@freeze_time("2026-08-05 12:00:00")
class AutorenewDryRunTests(TestCase):
    """``dry_run`` exists so operators can preview a charge batch safely.

    A dry run that mutated bookkeeping would either charge nobody forever
    (slots consumed) or charge everyone twice (attempts untracked); a dry
    run that sent the signal would charge cards from a "safe" command.
    """

    def setUp(self):
        self.user = _renewable_user("dryrun", datetime.date(2026, 8, 6))
        self.signals = []
        receiver = lambda sender, user, **kwargs: self.signals.append(
            user
        )  # noqa: E731
        account_automatic_renewal.connect(receiver)
        self.addCleanup(account_automatic_renewal.disconnect, receiver)

    def test_dry_run_reports_but_touches_nothing(self):
        candidates = autorenew_account(dry_run=True)

        self.assertIn(self.user, candidates)
        self.assertEqual(self.signals, [])
        self.user.userplan.recurring.refresh_from_db()
        self.assertIsNone(self.user.userplan.recurring.last_renewal_attempt)

    def test_dry_run_does_not_consume_the_slot(self):
        autorenew_account(dry_run=True)
        attempted = autorenew_account()

        self.assertIn(self.user, attempted)
        self.assertEqual(self.signals, [self.user])


@freeze_time("2026-08-05 12:00:00")
class ExpirationReminderTests(TestCase):
    """``PLANS_EXPIRATION_REMIND`` drives the pre-expiry warning emails.

    The windows were swept to local dates in the #236 fix with no test
    pinning them: a reminder must fire exactly on the configured
    days-before, not a day early or late.
    """

    def _user_expiring_in(self, days):
        return _renewable_user(
            f"expiring{days}", timezone.localdate() + datetime.timedelta(days=days)
        )

    @override_settings(PLANS_EXPIRATION_REMIND=[3])
    def test_reminder_fires_exactly_on_the_configured_day(self):
        self._user_expiring_in(3)

        expire_account()

        reminders = [m for m in mail.outbox if "expir" in m.subject.lower()]
        self.assertEqual(len(reminders), 1)

    @override_settings(PLANS_EXPIRATION_REMIND=[3])
    def test_no_reminder_on_neighboring_days(self):
        self._user_expiring_in(2)
        self._user_expiring_in(4)

        expire_account()

        self.assertEqual(mail.outbox, [])


class AutorenewCalendarEdgeTests(TestCase):
    """Slot bookkeeping edges: DST transitions and the max-age boundary."""

    def _attempts_at(self, user, *instants):
        attempts = []
        for instant in instants:
            with freeze_time(instant):
                attempts.append(sum(1 for u in autorenew_account() if u == user))
        return attempts

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=1, hours=3)],
        TIME_ZONE="Europe/Prague",
    )
    def test_dst_transition_day_still_attempts_exactly_once(self):
        # Prague springs forward on 2026-03-29: the local day is 23 hours
        # long. Calendar-date slot bookkeeping must not skip or double the
        # attempt around the jump.
        user = _renewable_user("dst", datetime.date(2026, 3, 30))

        attempts = self._attempts_at(
            user,
            "2026-03-28 19:01:00",
            "2026-03-28 20:01:00",
            "2026-03-29 05:01:00",
            "2026-03-29 21:01:00",
        )

        self.assertEqual(sum(attempts), 1, attempts)

    @override_settings(
        PLANS_AUTORENEW_SCHEDULE=[datetime.timedelta(days=-1)],
        PLANS_AUTORENEW_MAX_DAYS_AFTER_EXPIRY=datetime.timedelta(days=30),
    )
    @freeze_time("2026-08-05 12:00:00")
    def test_max_days_after_expiry_boundary_is_day_exact(self):
        # The -1d slot's window reaches back exactly 30 days; the day-31
        # account must be left alone. Off-by-one here either abandons
        # recoverable accounts or charges cards a month after churn.
        included = _renewable_user(
            "included", timezone.localdate() - datetime.timedelta(days=31)
        )
        excluded = _renewable_user(
            "excluded", timezone.localdate() - datetime.timedelta(days=32)
        )

        attempted = autorenew_account()

        self.assertIn(included, attempted)
        self.assertNotIn(excluded, attempted)
