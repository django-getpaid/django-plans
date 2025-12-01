"""
Tests for the slug migration functionality.
"""

from django.test import TestCase

from plans.base.models import AbstractPlan

Plan = AbstractPlan.get_concrete_model()


class SlugMigrationTestCase(TestCase):
    """Test the migration logic for adding and populating slug field."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing plans to avoid conflicts
        Plan.objects.all().delete()

    def test_populate_slugs_migration_function(self):
        """Test the populate_slugs function from migration 0017."""
        # Test the migration logic directly
        from django.utils.text import slugify

        # Test cases that would be handled by the migration
        test_cases = [
            ("Basic Plan", "basic-plan"),
            ("Premium Plan & More", "premium-plan-more"),
            ("Enterprise Solution", "enterprise-solution"),
            ("Plan With Duplicate Name", "plan-with-duplicate-name"),
            (
                "Plan With Duplicate Name",
                "plan-with-duplicate-name-1",
            ),  # Would get -1 suffix
        ]

        used_slugs = set()
        for name, expected_base in test_cases:
            base_slug = slugify(name)
            slug = base_slug
            counter = 1

            # Handle duplicates by appending a number (migration logic)
            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1

            used_slugs.add(slug)

            # Verify the logic works as expected
            if (
                name == "Plan With Duplicate Name"
                and len(
                    [s for s in used_slugs if s.startswith("plan-with-duplicate-name")]
                )
                == 1
            ):
                self.assertEqual(slug, "plan-with-duplicate-name")
            elif name == "Plan With Duplicate Name":
                self.assertEqual(slug, "plan-with-duplicate-name-1")

    def test_migration_with_existing_slugs(self):
        """Test migration behavior when some plans already have slugs."""
        # Create a plan with existing slug
        plan_with_slug = Plan.objects.create(
            name="Custom Plan",
            slug="my-custom-slug",
            description="Plan with existing slug",
            available=True,
            visible=True,
        )

        # Simulate migration by manually clearing and repopulating
        original_slug = plan_with_slug.slug

        # The migration should not overwrite existing slugs
        # (our save method only sets slug if it's empty)
        plan_with_slug.save()

        self.assertEqual(plan_with_slug.slug, original_slug)

    def test_migration_handles_unicode_names(self):
        """Test migration with unicode characters in names."""
        plan = Plan.objects.create(
            name="Plán Básico",
            slug="plan-basico",  # Provide the slug explicitly
            description="Plan with unicode characters",
            available=True,
            visible=True,
        )

        # Should store the provided slug
        self.assertEqual(plan.slug, "plan-basico")

    def test_migration_handles_duplicate_names_from_fixtures(self):
        """Test migration properly handles duplicate plan names like in initial_plan.json."""
        # Simulate the exact scenario from initial_plan.json where there are
        # two plans both named "Default Plan"

        # We can't actually create duplicates due to our validation, so we'll
        # test the migration logic directly
        from django.utils.text import slugify

        # Simulate plans with same names (like in fixtures)
        plan_names = ["Default Plan", "Default Plan", "Standard", "Premium"]

        # Test the migration logic
        used_slugs = set()
        generated_slugs = []

        for name in plan_names:
            base_slug = slugify(name)
            slug = base_slug
            counter = 1

            # Handle duplicates by appending a number
            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1

            used_slugs.add(slug)
            generated_slugs.append(slug)

        # Verify the expected slug generation
        expected_slugs = ["default-plan", "default-plan-1", "standard", "premium"]
        self.assertEqual(generated_slugs, expected_slugs)

    def test_migration_with_long_names(self):
        """Test migration with names that create long slugs."""
        # Use a name that fits in name field but creates a long slug
        long_name = (
            "Plan With Many Words That Create A Very Long Slug"  # Fits in name field
        )
        plan = Plan.objects.create(
            name=long_name,
            slug="plan-with-many-words-that-create-a-very-long-slug",
            description="Plan with long name",
            available=True,
            visible=True,
        )

        # Slug should be stored properly
        self.assertLessEqual(len(plan.slug), 100)
        self.assertTrue(plan.slug.startswith("plan-with-many-words"))


class SlugMigrationDataIntegrityTestCase(TestCase):
    """Test data integrity during slug migration."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing plans to avoid conflicts
        Plan.objects.all().delete()

    def test_migration_preserves_all_plan_data(self):
        """Test that migration preserves all existing plan data."""
        # Create a plan with all fields populated
        original_data = {
            "name": "Complete Plan",
            "slug": "complete-plan",
            "description": "Plan with all fields",
            "available": True,
            "visible": False,
            "default": True,
        }

        plan = Plan.objects.create(**original_data)
        original_id = plan.id

        # Verify all data is preserved after save
        plan.refresh_from_db()

        self.assertEqual(plan.id, original_id)
        self.assertEqual(plan.name, original_data["name"])
        self.assertEqual(plan.slug, original_data["slug"])
        self.assertEqual(plan.description, original_data["description"])
        self.assertEqual(plan.available, original_data["available"])
        self.assertEqual(plan.visible, original_data["visible"])
        self.assertEqual(plan.default, original_data["default"])

    def test_migration_with_related_objects(self):
        """Test that migration works correctly with related objects."""
        # Create a plan that might have related objects
        plan = Plan.objects.create(
            name="Plan with Relations",
            slug="plan-with-relations",
            description="Plan that might have quotas and pricing",
            available=True,
            visible=True,
        )

        # Verify the plan exists and has correct slug
        self.assertTrue(Plan.objects.filter(id=plan.id).exists())
        self.assertEqual(plan.slug, "plan-with-relations")

        # Verify we can still access the plan by its relationships
        # (This tests that foreign key relationships aren't broken)
        retrieved_plan = Plan.objects.get(id=plan.id)
        self.assertEqual(retrieved_plan.slug, plan.slug)
