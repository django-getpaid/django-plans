from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from freezegun import freeze_time
from model_bakery import baker

from plans.base.models import AbstractUserPlan
from plans.signals import activate_user_plan

User = get_user_model()
UserPlan = AbstractUserPlan.get_concrete_model()


@freeze_time("2024-01-15 12:00:00")
@override_settings(PLANS_DEFAULT_GRACE_PERIOD=14)
class InitializeUserPlanTests(TestCase):
    def _user_plan(self, priced, **kwargs):
        user = baker.make(User)
        plan = baker.make("Plan")
        if priced:
            baker.make("PlanPricing", plan=plan, pricing__period=30, price=10)
        return baker.make("UserPlan", user=user, plan=plan, **kwargs)

    def test_activating_a_paid_plan_starts_the_grace_period(self):
        user_plan = self._user_plan(priced=True, active=False, expire=None)

        activate_user_plan.send(sender=None, user=user_plan.user)

        user_plan.refresh_from_db()
        self.assertTrue(user_plan.active)
        self.assertEqual(user_plan.expire, date(2024, 1, 29))

    def test_activating_a_plan_without_pricing_keeps_it_without_expiry(self):
        user_plan = self._user_plan(priced=False, active=False, expire=None)

        activate_user_plan.send(sender=None, user=user_plan.user)

        user_plan.refresh_from_db()
        self.assertTrue(user_plan.active)
        self.assertIsNone(user_plan.expire)

    def test_activating_an_active_plan_keeps_its_expiry(self):
        user_plan = self._user_plan(priced=True, active=True, expire=date(2024, 3, 1))

        activate_user_plan.send(sender=None, user=user_plan.user)

        user_plan.refresh_from_db()
        self.assertEqual(user_plan.expire, date(2024, 3, 1))

    def test_activating_a_user_without_a_plan_does_nothing(self):
        user = baker.make(User)

        activate_user_plan.send(sender=None, user=user)

        self.assertFalse(UserPlan.objects.filter(user=user).exists())
