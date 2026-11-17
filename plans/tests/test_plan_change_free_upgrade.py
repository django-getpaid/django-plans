from decimal import Decimal

from django.test import TestCase

from plans.base.models import AbstractPlan
from plans.plan_change import StandardPlanChangePolicy

Plan = AbstractPlan.get_concrete_model()


class FreeSmallUpgradesPolicy(StandardPlanChangePolicy):
    FREE_UPGRADE = Decimal("10.00")


class FreeUpgradeThresholdTests(TestCase):
    fixtures = ["initial_plan", "test_django-plans_auth", "test_django-plans_plans"]

    def setUp(self):
        self.standard = Plan.objects.get(name="Standard")
        self.premium = Plan.objects.get(name="Premium")

    def test_upgrade_cheaper_than_the_threshold_is_free(self):
        self.assertEqual(
            StandardPlanChangePolicy().get_change_price(
                self.standard, self.premium, 23
            ),
            Decimal("8.60"),
        )
        self.assertIsNone(
            FreeSmallUpgradesPolicy().get_change_price(self.standard, self.premium, 23)
        )

    def test_upgrade_above_the_threshold_is_charged_in_full(self):
        self.assertEqual(
            FreeSmallUpgradesPolicy().get_change_price(self.standard, self.premium, 53),
            Decimal("19.82"),
        )
