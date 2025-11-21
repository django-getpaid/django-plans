from decimal import Decimal

from django.test import TestCase, override_settings

from plans.taxation.eu import EUTaxationPolicy


class EUTaxationTEDBIntegrationTest(TestCase):
    """Simple integration test for TEDB functionality."""

    @override_settings(PLANS_TAX_COUNTRY="DE")
    def test_fallback_to_static_table_works(self):
        """Test that fallback to static table works when TEDB is unavailable."""
        # This should use static table since TEDB is not fully implemented yet
        rate = EUTaxationPolicy.get_default_tax()

        # Should return Germany's static rate
        self.assertEqual(rate, Decimal("19"))

    @override_settings(PLANS_TAX_COUNTRY="DE")
    def test_get_tax_rate_uses_fallback(self):
        """Test that get_tax_rate uses static table fallback."""
        rate, success = EUTaxationPolicy.get_tax_rate(None, "FR")

        # Should return France's static rate
        self.assertEqual(rate, Decimal("20"))
        self.assertTrue(success)

    @override_settings(PLANS_TAX_COUNTRY="DE")
    def test_tedb_client_initialization(self):
        """Test that TEDB client can be initialized without errors."""
        # This should not raise any exceptions
        client = EUTaxationPolicy._get_tedb_client()
        self.assertIsNotNone(client)

    @override_settings(PLANS_TAX_COUNTRY="DE")
    def test_get_vat_rate_from_tedb_fallback(self):
        """Test TEDB fallback mechanism."""
        # Should fall back to static table
        rate = EUTaxationPolicy._get_vat_rate_from_tedb("DE")
        self.assertEqual(rate, Decimal("19"))

    @override_settings(PLANS_TAX_COUNTRY="DE")
    def test_updated_vat_rates_in_static_table(self):
        """Test that recently updated VAT rates are correct in static table."""
        # Test recently changed rates
        recent_changes = {
            "EE": Decimal("24"),  # Estonia (changed to 24% in July 2025)
            "FI": Decimal("25.5"),  # Finland (changed from 24% in Sep 2024)
            "SK": Decimal("23"),  # Slovakia (changed from 20% in Jan 2025)
            "RO": Decimal("21"),  # Romania (changed from 19% in Aug 2025)
        }

        for country, expected_rate in recent_changes.items():
            actual_rate = EUTaxationPolicy.EU_COUNTRIES_VAT.get(country)
            self.assertEqual(
                actual_rate,
                expected_rate,
                f"VAT rate for {country} should be {expected_rate}%, got {actual_rate}%",
            )
