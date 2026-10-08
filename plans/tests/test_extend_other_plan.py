from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.timezone import localdate

from plans.models import PlanPricing

User = get_user_model()


class ExtendAccountWithAnotherPlanTests(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def test_a_paid_order_for_another_running_plan_is_logged_as_an_error(self):
        user_plan = User.objects.get(username="test1").userplan
        user_plan.expire = localdate() + timedelta(days=10)
        user_plan.save()
        other = PlanPricing.objects.exclude(plan=user_plan.plan).first()

        with self.assertLogs("accounts", level="ERROR") as logs:
            self.assertFalse(user_plan.extend_account(other.plan, other.pricing))

        self.assertIn("the paid order extends nothing", logs.output[0])
        user_plan.refresh_from_db()
        self.assertEqual(user_plan.expire, localdate() + timedelta(days=10))
