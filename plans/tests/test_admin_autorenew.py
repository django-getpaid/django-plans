from unittest import mock

from django.contrib.admin import site as admin_site
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from model_bakery import baker

from plans.admin import autorenew_payment
from plans.base.models import AbstractUserPlan
from plans.models import Plan
from plans.signals import account_automatic_renewal

User = get_user_model()
UserPlan = AbstractUserPlan.get_concrete_model()


class AutorenewPaymentActionTests(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.request = RequestFactory().post("/admin/plans/userplan/")
        self.request.session = {}
        self.request._messages = FallbackStorage(self.request)
        self.modeladmin = admin_site._registry[UserPlan]
        self.receiver = mock.Mock()
        account_automatic_renewal.connect(self.receiver)
        self.addCleanup(account_automatic_renewal.disconnect, self.receiver)

    def run_action(self, *user_plans):
        autorenew_payment(
            self.modeladmin,
            self.request,
            UserPlan.objects.filter(pk__in=[up.pk for up in user_plans]),
        )
        return [(m.level_tag, str(m)) for m in get_messages(self.request)]

    def paid_user_plan(self, username):
        user_plan = User.objects.get(username=username).userplan
        user_plan.plan = Plan.objects.filter(planpricing__isnull=False).first()
        user_plan.save()
        return user_plan

    def test_renews_a_plan_with_a_recurring_payment(self):
        user_plan = self.paid_user_plan("test1")
        baker.make("RecurringUserPlan", user_plan=user_plan)

        self.assertEqual(
            self.run_action(user_plan),
            [("success", "Automatic renewal requested for 1 plan(s).")],
        )
        self.receiver.assert_called_once()
        self.assertEqual(self.receiver.call_args.kwargs["user"], user_plan.user)

    def test_skips_a_plan_without_a_recurring_payment(self):
        user_plan = self.paid_user_plan("test1")

        self.assertEqual(
            self.run_action(user_plan),
            [("warning", "test1: no recurring payment is set up, nothing to renew.")],
        )
        self.receiver.assert_not_called()

    def test_skips_a_free_plan(self):
        user_plan = User.objects.get(username="test1").userplan
        user_plan.plan = baker.make(Plan, name="Free")
        user_plan.save()
        baker.make("RecurringUserPlan", user_plan=user_plan)

        self.assertEqual(
            self.run_action(user_plan),
            [("warning", "test1: plan Free is free, nothing to renew.")],
        )
        self.receiver.assert_not_called()
