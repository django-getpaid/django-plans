from django.core.exceptions import ValidationError
from django.test import TestCase
from model_bakery import baker

from plans.models import Plan


class DefaultPlanFlagTests(TestCase):
    """``Plan.default`` is unique-nullable: True at most once, everything
    else must be stored as NULL ("Unknown").

    The admin offers "No" (False) as a choice, but storing False twice
    violates the unique constraint and greeted the second save with a bare
    IntegrityError (issue #97). False and NULL mean the same thing -- the
    field's own help_text says so -- so False is normalized to NULL on save.
    """

    def test_two_non_default_plans_save_without_error(self):
        a = baker.make("Plan", name="A", default=False)
        b = baker.make("Plan", name="B", default=False)

        a.refresh_from_db()
        b.refresh_from_db()
        self.assertIsNone(a.default)
        self.assertIsNone(b.default)

    def test_the_single_default_survives_normalization(self):
        plan = baker.make("Plan", name="D", default=True)

        plan.refresh_from_db()
        self.assertTrue(plan.default)

    def test_second_default_fails_loud_but_friendly(self):
        baker.make("Plan", name="D1", default=True)
        second = Plan(name="D2", default=True)

        with self.assertRaises(ValidationError):
            second.full_clean()
