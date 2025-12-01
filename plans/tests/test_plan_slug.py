"""
Tests for Plan model slug functionality.
"""

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import RequestFactory, TestCase

from plans.admin import PlanAdmin
from plans.base.models import AbstractPlan

User = get_user_model()
Plan = AbstractPlan.get_concrete_model()


class PlanSlugTestCase(TestCase):
    """Test slug functionality for Plan model."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        # Clear any existing plans to avoid conflicts
        Plan.objects.all().delete()

    def test_slug_field_exists(self):
        """Test that slug field exists and can be set."""
        plan = Plan.objects.create(
            name="Premium Plan",
            slug="premium-plan",
            description="A premium plan for testing",
            available=True,
            visible=True,
        )

        self.assertEqual(plan.slug, "premium-plan")

    def test_slug_can_be_set_manually(self):
        """Test that slug can be set manually."""
        plan = Plan.objects.create(
            name="Pro Plan & More!",
            slug="custom-pro-slug",
            description="Plan with custom slug",
            available=True,
            visible=True,
        )

        self.assertEqual(plan.slug, "custom-pro-slug")

    def test_slug_not_overwritten_if_provided(self):
        """Test that manually provided slug is not overwritten."""
        plan = Plan.objects.create(
            name="Custom Plan",
            slug="my-custom-slug",
            description="Plan with custom slug",
            available=True,
            visible=True,
        )

        self.assertEqual(plan.slug, "my-custom-slug")

    def test_slug_uniqueness_constraint(self):
        """Test that slug field enforces uniqueness at database level."""
        Plan.objects.create(
            name="First Plan",
            slug="test-slug",
            description="First plan",
            available=True,
            visible=True,
        )

        # Second plan with same slug should raise IntegrityError
        plan2 = Plan(
            name="Second Plan",
            slug="test-slug",  # Same slug
            description="Second plan",
            available=True,
            visible=True,
        )

        with self.assertRaises(IntegrityError):
            plan2.save()

    def test_plan_str_method_unchanged(self):
        """Test that __str__ method still returns name."""
        plan = Plan.objects.create(
            name="Test Plan",
            slug="test-plan",
            description="Test plan",
            available=True,
            visible=True,
        )

        self.assertEqual(str(plan), "Test Plan")


class PlanSlugMigrationTestCase(TestCase):
    """Test migration logic for populating slugs from existing names."""

    def test_migration_slug_population_logic(self):
        """Test the logic used in migration to populate slugs."""
        # Test the slugify logic that would be used in migration
        from django.utils.text import slugify

        # Test various name patterns
        test_cases = [
            ("Basic Plan", "basic-plan"),
            ("Premium Plan & More!", "premium-plan-more"),
            ("Plán Básico", "plan-basico"),
            ("Plan   With   Spaces", "plan-with-spaces"),
        ]

        for name, expected_slug in test_cases:
            actual_slug = slugify(name)
            self.assertEqual(actual_slug, expected_slug, f"Failed for name: {name}")

    def test_slug_uniqueness_enforced(self):
        """Test that slug uniqueness is enforced."""
        # Create first plan
        Plan.objects.create(
            name="Standard Plan",
            slug="standard-plan",
            description="First standard plan",
            available=True,
            visible=True,
        )

        # Try to create second plan with same slug - should fail
        with self.assertRaises(IntegrityError):
            Plan.objects.create(
                name="Another Plan",
                slug="standard-plan",  # Same slug
                description="Second plan with same slug",
                available=True,
                visible=True,
            )


class PlanAdminSlugTestCase(TestCase):
    """Test admin functionality for Plan slug field."""

    def setUp(self):
        """Set up admin test data."""
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = PlanAdmin(Plan, self.site)

        # Create a superuser for admin tests
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="adminpass"
        )

    def test_slug_in_list_display(self):
        """Test that slug is included in admin list display."""
        self.assertIn("slug", self.admin.list_display)

    def test_slug_in_search_fields(self):
        """Test that slug is included in admin search fields."""
        self.assertIn("slug", self.admin.search_fields)

    def test_prepopulated_fields_for_new_objects(self):
        """Test that slug is prepopulated from name for new objects."""
        self.assertEqual(self.admin.prepopulated_fields, {"slug": ("name",)})

    def test_slug_always_editable(self):
        """Test that slug is always editable in admin."""
        # Create a plan
        plan = Plan.objects.create(
            name="Test Plan",
            description="Test plan",
            available=True,
            visible=True,
        )

        # Test readonly fields for existing object
        request = self.factory.get("/admin/plans/plan/")
        request.user = self.superuser

        readonly_fields = self.admin.get_readonly_fields(request, plan)
        self.assertNotIn("slug", readonly_fields)

        # Test readonly fields for new object
        readonly_fields = self.admin.get_readonly_fields(request, None)
        self.assertNotIn("slug", readonly_fields)

    def test_admin_preserves_base_readonly_fields(self):
        """Test that admin preserves base readonly fields."""
        request = self.factory.get("/admin/plans/plan/")
        request.user = self.superuser

        readonly_fields = self.admin.get_readonly_fields(request, None)
        self.assertIn("created", readonly_fields)
        self.assertIn("updated_at", readonly_fields)


class PlanSlugEdgeCasesTestCase(TestCase):
    """Test edge cases for Plan slug functionality."""

    def test_slug_max_length_constraint(self):
        """Test that slug field respects max_length constraint."""
        # Try to create plan with slug that's too long
        long_slug = "a" * 101  # 101 characters - exceeds max_length

        with self.assertRaises(Exception):  # Could be ValidationError or DataError
            Plan.objects.create(
                name="Test Plan",
                slug=long_slug,
                description="Plan with too long slug",
                available=True,
                visible=True,
            )

    def test_slug_with_numbers_and_hyphens(self):
        """Test that slug field accepts numbers and hyphens."""
        plan = Plan.objects.create(
            name="Plan 2024 Version 1.5",
            slug="plan-2024-version-1-5",
            description="Plan with numbers and hyphens",
            available=True,
            visible=True,
        )

        self.assertEqual(plan.slug, "plan-2024-version-1-5")

    def test_slug_field_behavior(self):
        """Test slug field behavior."""
        # Slug field should accept valid slugs
        plan = Plan.objects.create(
            name="Test Plan",
            slug="test-plan",
            description="Plan with valid slug",
            available=True,
            visible=True,
        )

        self.assertEqual(plan.slug, "test-plan")
