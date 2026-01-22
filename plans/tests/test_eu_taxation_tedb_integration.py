from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from zeep.exceptions import XMLSyntaxError

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
    @patch("plans.taxation.tedb_client.Client")
    def test_fallback_when_tedb_returns_html_error_page(self, mock_client_class):
        """
        Test that system falls back to static rates when TEDB returns HTML error page.

        This simulates the production issue where the EU server returns:
        "Server temporarily unavailable" HTML page instead of WSDL XML.
        """
        # Simulate the EU server returning an HTML error page
        mock_client_class.side_effect = XMLSyntaxError(
            "Invalid XML content received (xmlParseEntityRef: no name, line 12, column 48)"
        )

        # Clear the cached TEDB client to force re-initialization
        if hasattr(EUTaxationPolicy, "_tedb_client"):
            delattr(EUTaxationPolicy, "_tedb_client")

        # This should NOT crash, but fall back to static table
        rate = EUTaxationPolicy._get_vat_rate_from_tedb("DE")

        # Should return Germany's static rate
        self.assertEqual(rate, Decimal("19"))

    @override_settings(PLANS_TAX_COUNTRY="DE")
    @patch("plans.taxation.tedb_client.Client")
    def test_get_tax_rate_falls_back_on_xml_syntax_error(self, mock_client_class):
        """
        Test that get_tax_rate (used in actual user requests) falls back gracefully.

        This is the end-to-end test for the production error scenario.
        """
        # Simulate the EU server returning an HTML error page
        mock_client_class.side_effect = XMLSyntaxError(
            "Invalid XML content received (xmlParseEntityRef: no name, line 12, column 48)"
        )

        # Clear the cached TEDB client to force re-initialization
        if hasattr(EUTaxationPolicy, "_tedb_client"):
            delattr(EUTaxationPolicy, "_tedb_client")

        # This should NOT crash the request, but use static rates
        rate, success = EUTaxationPolicy.get_tax_rate(None, "FR")

        # Should return France's static rate
        self.assertEqual(rate, Decimal("20"))
        self.assertTrue(success)

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

    @override_settings(PLANS_TAX_COUNTRY="DE")
    def test_static_vat_rates_match_tedb(self):
        """
        Validate that static VAT table matches live TEDB data.

        This test queries the actual TEDB API and compares with our static table.
        It will FAIL if rates don't match, indicating either:
        - VAT rates have changed and need updating
        - Bug in TEDB parsing (e.g., returning regional rates)

        This test is designed to catch issues like Spain returning 7% (Canary Islands)
        instead of 21% (mainland).
        """
        tedb_client = EUTaxationPolicy._get_tedb_client()

        if not tedb_client.client:
            self.skipTest("TEDB client not available")

        # Test all countries in our static table
        for country_code, static_rate in EUTaxationPolicy.EU_COUNTRIES_VAT.items():
            tedb_rate = tedb_client.get_vat_rate(country_code)

            self.assertIsNotNone(
                tedb_rate,
                f"{country_code}: TEDB returned None (service error or no data)",
            )

            self.assertEqual(
                tedb_rate,
                static_rate,
                f"{country_code}: TEDB returned {tedb_rate}% but static table has {static_rate}% "
                f"- either VAT changed or there's a bug (e.g., regional rate like Canary Islands)",
            )
