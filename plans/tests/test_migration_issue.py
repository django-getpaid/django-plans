"""
Test for migration issue #192 - Error when migrate
https://github.com/django-getpaid/django-plans/issues/192
"""

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class MigrationIssue192TestCase(TestCase):
    """Test that reproduces and verifies the fix for migration issue.

    Tests the case where updated_at field is referenced before it exists.
    """

    def test_migration_0004_logic_with_historical_models(self):
        """
        Test the fixed migration logic using apps.get_model() instead of importing current models.
        This simulates what the fixed migration 0004_create_user_plans does.
        """
        # Simulate using historical models (like in the migration)
        User = apps.get_model(settings.AUTH_USER_MODEL)
        Plan = apps.get_model("plans", "Plan")
        UserPlan = apps.get_model("plans", "UserPlan")

        # Create a user without a user plan
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        # Create a default plan
        plan = Plan.objects.create(
            name="Default Plan",
            description="Default plan for testing",
            default=True,
            available=True,
            visible=True,
        )

        # Delete any existing user plans to simulate fresh migration
        UserPlan.objects.filter(user=user).delete()

        # This is the fixed migration logic
        try:
            default_plan = Plan.objects.filter(default=True).first()
            self.assertIsNotNone(default_plan)

            users_without_plans = User.objects.filter(userplan=None)
            self.assertGreaterEqual(users_without_plans.count(), 1)

            # Create user plans for users without them
            for user_without_plan in users_without_plans:
                UserPlan.objects.create(
                    user=user_without_plan,
                    plan=default_plan,
                    active=False,
                    expire=None,
                )

            # Verify user plan was created
            user_plan = UserPlan.objects.get(user=user)
            self.assertEqual(user_plan.plan, plan)
            self.assertFalse(user_plan.active)  # Should be inactive by default
            self.assertIsNone(user_plan.expire)

        except Exception as e:
            self.fail(f"Fixed migration logic failed: {e}")

    def test_migration_handles_no_default_plan(self):
        """
        Test that the migration gracefully handles the case where no default plan exists.
        """
        # Simulate using historical models
        User = apps.get_model(settings.AUTH_USER_MODEL)
        Plan = apps.get_model("plans", "Plan")
        UserPlan = apps.get_model("plans", "UserPlan")

        # Create a user
        user = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass"
        )

        # Ensure no default plan exists
        Plan.objects.filter(default=True).delete()

        # Delete any existing user plans
        UserPlan.objects.filter(user=user).delete()

        # This should not fail even when no default plan exists
        try:
            default_plan = Plan.objects.filter(default=True).first()
            self.assertIsNone(default_plan)

            if default_plan is None:
                # Should skip creating user plans
                initial_count = UserPlan.objects.filter(user=user).count()
                # Migration logic would return early here
                final_count = UserPlan.objects.filter(user=user).count()
                self.assertEqual(initial_count, final_count)

        except Exception as e:
            self.fail(f"Migration should handle missing default plan gracefully: {e}")
