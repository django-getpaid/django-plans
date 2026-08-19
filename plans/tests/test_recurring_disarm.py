"""``set_all_fields_default`` must be safe to persist on its own.

The method nulls every renewal field, but ``currency`` was NOT NULL in
the database -- the only safe use was django-plans' own re-arm flow,
which immediately assigns a new currency before saving. Any external
caller disarming a recurring plan (plan switched to free, provider
token revoked, ...) crashed on save with an IntegrityError.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from plans.models import Plan, RecurringUserPlan, UserPlan

User = get_user_model()


class SetAllFieldsDefaultTests(TestCase):
    def test_disarm_persists_standalone(self):
        user = User.objects.create_user("payer", "payer@example.com")
        plan = Plan.objects.create(name="Paid", available=True, created="2026-01-01")
        userplan = UserPlan.objects.create(user=user, plan=plan, active=True)
        recurring = RecurringUserPlan.objects.create(
            user_plan=userplan,
            payment_provider="default",
            amount=10,
            currency="EUR",
            token="token",
            token_verified=True,
        )

        recurring.set_all_fields_default()
        recurring.save()

        recurring.refresh_from_db()
        self.assertIsNone(recurring.currency)
        self.assertIsNone(recurring.payment_provider)
        self.assertIsNone(recurring.token)
        self.assertFalse(recurring.token_verified)
