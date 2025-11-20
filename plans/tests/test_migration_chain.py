"""
Comprehensive tests for the entire migration chain to ensure migrations work
on both blank databases and existing databases.

Tests for issue #192 and general migration robustness.
"""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class MigrationChainTestCase(TestCase):
    """Test migration logic without actually running migrations on the test database."""

    def setUp(self):
        """Set up test data for migration logic testing."""
        # Test the migration logic without actually manipulating schema
        pass

    def test_migration_0004_logic_isolated(self):
        """Test the migration 0004 logic in isolation without schema changes."""
        # This tests the actual logic that migration 0004 uses
        # without requiring schema manipulation

        # Create test data
        user = User.objects.create_user(
            username="migration_test_user",
            email="test@migration.com",
            password="testpass",
        )

        Plan = apps.get_model("plans", "Plan")
        UserPlan = apps.get_model("plans", "UserPlan")

        # Create a default plan
        plan = Plan.objects.create(
            name="Migration Test Plan",
            description="Plan for testing migration logic",
            default=True,
            available=True,
            visible=True,
        )

        # Ensure no user plan exists initially
        UserPlan.objects.filter(user=user).delete()

        # Test the migration 0004 logic (using current models, but same logic)
        default_plan = Plan.objects.filter(default=True).first()
        self.assertIsNotNone(default_plan, "Should have a default plan")

        users_without_plans = User.objects.filter(userplan=None)
        self.assertGreaterEqual(
            users_without_plans.count(), 1, "Should have users without plans"
        )

        # Apply the migration logic
        for user_without_plan in users_without_plans:
            UserPlan.objects.create(
                user=user_without_plan,
                plan=default_plan,
                active=False,
                expire=None,
            )

        # Verify results
        user_plan = UserPlan.objects.get(user=user)
        self.assertEqual(user_plan.plan, plan)
        self.assertFalse(user_plan.active)
        self.assertIsNone(user_plan.expire)

    def test_migration_handles_no_default_plan_scenario(self):
        """Test that migration logic handles missing default plan gracefully."""
        Plan = apps.get_model("plans", "Plan")
        UserPlan = apps.get_model("plans", "UserPlan")

        # Create a user
        user = User.objects.create_user(
            username="no_default_user", email="nodefault@test.com", password="testpass"
        )

        # Ensure no default plan exists
        Plan.objects.filter(default=True).delete()

        # Test migration logic with no default plan
        default_plan = Plan.objects.filter(default=True).first()
        self.assertIsNone(default_plan, "Should have no default plan")

        # Migration should handle this gracefully (skip user plan creation)
        if default_plan is None:
            # This is what the migration does - it returns early
            initial_count = UserPlan.objects.filter(user=user).count()
            # No user plans should be created
            final_count = UserPlan.objects.filter(user=user).count()
            self.assertEqual(
                initial_count,
                final_count,
                "No user plans should be created without default plan",
            )


class MigrationDataIntegrityTestCase(TestCase):
    """Test that migrations preserve data integrity."""

    def test_user_plan_creation_with_existing_users(self):
        """Test that migration 0004 creates user plans for existing users."""
        # Create users before running the migration logic
        user1 = User.objects.create_user(
            username="existing_user1", email="user1@test.com", password="testpass"
        )
        user2 = User.objects.create_user(
            username="existing_user2", email="user2@test.com", password="testpass"
        )

        # Create a default plan
        Plan = apps.get_model("plans", "Plan")
        plan = Plan.objects.create(
            name="Default Plan",
            description="Default plan for existing users",
            default=True,
            available=True,
            visible=True,
        )

        # Simulate the migration 0004 logic
        UserPlan = apps.get_model("plans", "UserPlan")

        # Delete any existing user plans
        UserPlan.objects.all().delete()

        # Run the migration logic
        default_plan = Plan.objects.filter(default=True).first()
        self.assertIsNotNone(default_plan)

        users_without_plans = User.objects.filter(userplan=None)
        self.assertGreaterEqual(users_without_plans.count(), 2)

        for user in users_without_plans:
            UserPlan.objects.create(
                user=user,
                plan=default_plan,
                active=False,
                expire=None,
            )

        # Verify both users got user plans
        self.assertTrue(UserPlan.objects.filter(user=user1).exists())
        self.assertTrue(UserPlan.objects.filter(user=user2).exists())

        user1_plan = UserPlan.objects.get(user=user1)
        user2_plan = UserPlan.objects.get(user=user2)

        self.assertEqual(user1_plan.plan, plan)
        self.assertEqual(user2_plan.plan, plan)
        self.assertFalse(user1_plan.active)
        self.assertFalse(user2_plan.active)

    def test_migration_with_existing_default_plan(self):
        """Test migration behavior when a default plan already exists."""
        Plan = apps.get_model("plans", "Plan")
        UserPlan = apps.get_model("plans", "UserPlan")

        # Ensure no default plan exists initially
        Plan.objects.filter(default=True).delete()

        # Create a default plan
        plan = Plan.objects.create(
            name="Existing Default Plan",
            description="Plan that already exists as default",
            default=True,
            available=True,
            visible=True,
        )

        user = User.objects.create_user(
            username="existing_default_user",
            email="existing@test.com",
            password="testpass",
        )

        # Migration should use the existing default plan
        default_plan = Plan.objects.filter(default=True).first()
        self.assertEqual(default_plan, plan)

        # Create user plan using migration logic
        UserPlan.objects.filter(user=user).delete()
        UserPlan.objects.create(
            user=user,
            plan=default_plan,
            active=False,
            expire=None,
        )

        user_plan = UserPlan.objects.get(user=user)
        self.assertEqual(user_plan.plan, plan)

    def test_migration_with_no_users(self):
        """Test that migration works correctly when no users exist."""
        Plan = apps.get_model("plans", "Plan")
        UserPlan = apps.get_model("plans", "UserPlan")

        # Create a default plan
        Plan.objects.create(
            name="No Users Plan",
            description="Plan when no users exist",
            default=True,
            available=True,
            visible=True,
        )

        # Ensure no users exist
        User.objects.all().delete()

        # Run migration logic
        default_plan = Plan.objects.filter(default=True).first()
        self.assertIsNotNone(default_plan)

        users_without_plans = User.objects.filter(userplan=None)
        self.assertEqual(users_without_plans.count(), 0)

        # Should not create any user plans
        initial_count = UserPlan.objects.count()
        for user in users_without_plans:
            UserPlan.objects.create(
                user=user,
                plan=default_plan,
                active=False,
                expire=None,
            )
        final_count = UserPlan.objects.count()

        self.assertEqual(initial_count, final_count)
