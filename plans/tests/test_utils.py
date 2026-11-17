from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from plans.taxation import TaxationPolicy
from plans.utils import get_currency, get_tax_rate

policy_calls = []


class FixedRatePolicy(TaxationPolicy):
    rate = Decimal("21")

    @classmethod
    def get_tax_rate(cls, tax_id, country_code, request=None):
        policy_calls.append((tax_id, country_code))
        return cls.rate, True


class NoTaxPolicy(FixedRatePolicy):
    rate = None


class CurrencyTests(SimpleTestCase):
    @override_settings(PLANS_CURRENCY="EURO")
    def test_currency_must_be_a_three_letter_code(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "PLANS_CURRENCY should be configured as 3-letter currency code.",
        ):
            get_currency()


class TaxRateTests(SimpleTestCase):
    def setUp(self):
        policy_calls.clear()

    @override_settings(PLANS_TAXATION_POLICY=None)
    def test_taxation_policy_is_required(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured, "PLANS_TAXATION_POLICY is not set"
        ):
            get_tax_rate("DE", "")

    @override_settings(PLANS_TAXATION_POLICY="plans.tests.test_utils.FixedRatePolicy")
    def test_rate_is_cached_in_the_session(self):
        request = SimpleNamespace(session={})

        self.assertEqual(get_tax_rate("DE", "", request), (Decimal("21"), True))
        self.assertEqual(get_tax_rate("DE", "", request), (Decimal("21"), True))

        self.assertEqual(policy_calls, [("", "DE")])

    @override_settings(PLANS_TAXATION_POLICY="plans.tests.test_utils.NoTaxPolicy")
    def test_cached_no_tax_stays_no_tax(self):
        request = SimpleNamespace(session={})

        self.assertEqual(get_tax_rate("US", "", request), (None, True))
        self.assertEqual(get_tax_rate("US", "", request), (None, True))

        self.assertEqual(policy_calls, [("", "US")])

    @override_settings(PLANS_TAX=Decimal("23"))
    def test_base_policy_default_tax_is_the_plans_tax_setting(self):
        self.assertEqual(TaxationPolicy.get_default_tax(), Decimal("23"))
