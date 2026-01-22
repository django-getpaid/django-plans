from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import TestCase
from requests.exceptions import ConnectionError
from zeep.exceptions import XMLSyntaxError

from plans.taxation.tedb_client import TEDBClient


class TEDBClientTest(TestCase):
    def setUp(self):
        self.client = TEDBClient()
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("plans.taxation.tedb_client.Client")
    def test_client_initialization_success(self, mock_client_class):
        """Test successful SOAP client initialization."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        client = TEDBClient()

        mock_client_class.assert_called_once_with(TEDBClient.WSDL_URL)
        self.assertEqual(client.client, mock_client)

    @patch("plans.taxation.tedb_client.Client")
    def test_client_initialization_failure(self, mock_client_class):
        """Test SOAP client initialization failure."""
        mock_client_class.side_effect = ConnectionError("Network error")

        client = TEDBClient()

        self.assertIsNone(client.client)

    @patch("plans.taxation.tedb_client.Client")
    def test_client_initialization_xml_syntax_error(self, mock_client_class):
        """Test SOAP client initialization when server returns HTML instead of WSDL."""
        # Simulate the EU server returning an HTML error page
        mock_client_class.side_effect = XMLSyntaxError(
            "Invalid XML content received (xmlParseEntityRef: no name, line 12, column 48)"
        )

        # This should not crash, but gracefully set client to None
        client = TEDBClient()

        self.assertIsNone(client.client)

    def test_cache_key_generation(self):
        """Test cache key generation."""
        key = self.client._get_cache_key("DE", "2025-01-01")
        expected = "tedb_vat_rate_DE_2025-01-01"
        self.assertEqual(key, expected)

    def test_cache_key_generation_default_date(self):
        """Test cache key generation with default date."""
        key = self.client._get_cache_key("DE")
        self.assertTrue(key.startswith("tedb_vat_rate_DE_"))

    @patch("plans.taxation.tedb_client.cache")
    def test_get_vat_rate_from_cache(self, mock_cache):
        """Test retrieving VAT rate from cache."""
        mock_cache.get.return_value = Decimal("19")

        rate = self.client.get_vat_rate("DE")

        self.assertEqual(rate, Decimal("19"))
        mock_cache.get.assert_called_once()

    def test_get_vat_rate_soap_success(self):
        """Test successful VAT rate retrieval from SOAP service."""
        # Mock the client to simulate no SOAP client available
        self.client.client = None

        rate = self.client.get_vat_rate("DE")

        # Should return None (will use static table fallback)
        self.assertIsNone(rate)

    def test_get_vat_rate_soap_network_error(self):
        """Test VAT rate retrieval with network error."""
        # Mock the client to simulate no SOAP client available
        self.client.client = None

        rate = self.client.get_vat_rate("DE")

        self.assertIsNone(rate)

    def test_get_vat_rate_soap_fault_error(self):
        """Test VAT rate retrieval with SOAP fault."""
        # Mock the client to simulate no SOAP client available
        self.client.client = None

        rate = self.client.get_vat_rate("DE")

        self.assertIsNone(rate)

    def test_get_vat_rate_no_client(self):
        """Test VAT rate retrieval when SOAP client is not available."""
        self.client.client = None

        rate = self.client.get_vat_rate("DE")

        self.assertIsNone(rate)

    @patch("plans.taxation.tedb_client.datetime")
    def test_regional_rate_filtering_spain(self, mock_datetime):
        """
        Test that regional rates are filtered correctly (Spain case).

        Spain has 2 STANDARD+DEFAULT rates in TEDB:
        - 7% for Canary Islands (with comment)
        - 21% for mainland (no comment)

        This test verifies we return 21% (mainland), not 7% (regional).
        """
        # Mock current date
        mock_datetime.now.return_value.strftime.return_value = "2025-11-01"

        # Create mock SOAP response structure for Spain
        mock_rate_canary = Mock()
        mock_rate_canary.memberState = "ES"
        mock_rate_canary.type = "STANDARD"
        mock_rate_canary.rate = Mock()
        mock_rate_canary.rate.type = "DEFAULT"
        mock_rate_canary.rate.value = 7.0
        mock_rate_canary.comment = "VAT - Canary Islands - "

        mock_rate_mainland = Mock()
        mock_rate_mainland.memberState = "ES"
        mock_rate_mainland.type = "STANDARD"
        mock_rate_mainland.rate = Mock()
        mock_rate_mainland.rate.type = "DEFAULT"
        mock_rate_mainland.rate.value = 21.0
        mock_rate_mainland.comment = None

        mock_response = Mock()
        mock_response.vatRateResults = [mock_rate_canary, mock_rate_mainland]

        # Mock the SOAP client
        mock_soap_client = Mock()
        mock_soap_client.service.retrieveVatRates.return_value = mock_response
        self.client.client = mock_soap_client

        # Execute
        rate = self.client.get_vat_rate("ES")

        # Verify: Should return 21 (mainland), not 7 (Canary Islands)
        self.assertEqual(rate, Decimal("21"))

        # Verify the rate was cached
        cached = cache.get(self.client._get_cache_key("ES", "2025-11-01"))
        self.assertEqual(cached, Decimal("21"))

    @patch("plans.taxation.tedb_client.datetime")
    def test_all_rates_have_comments_use_highest(self, mock_datetime):
        """
        Test fallback when all rates have comments (e.g., France).

        When all STANDARD+DEFAULT rates have comments, we should use the highest.
        """
        # Mock current date
        mock_datetime.now.return_value.strftime.return_value = "2025-11-01"

        # Create mock response with single rate with comment
        mock_rate = Mock()
        mock_rate.memberState = "FR"
        mock_rate.type = "STANDARD"
        mock_rate.rate = Mock()
        mock_rate.rate.type = "DEFAULT"
        mock_rate.rate.value = 20.0
        mock_rate.comment = "Article 278 of the General Tax Code"

        mock_response = Mock()
        mock_response.vatRateResults = [mock_rate]

        # Mock the SOAP client
        mock_soap_client = Mock()
        mock_soap_client.service.retrieveVatRates.return_value = mock_response
        self.client.client = mock_soap_client

        # Execute
        rate = self.client.get_vat_rate("FR")

        # Verify: Should return 20 (the only/highest rate)
        self.assertEqual(rate, Decimal("20"))

    @patch("plans.taxation.tedb_client.datetime")
    def test_decimal_normalization(self, mock_datetime):
        """Test that whole number rates are normalized (21.0 → 21)."""
        # Mock current date
        mock_datetime.now.return_value.strftime.return_value = "2025-11-01"

        # Create mock response with 21.0 (float from SOAP)
        mock_rate = Mock()
        mock_rate.memberState = "ES"
        mock_rate.type = "STANDARD"
        mock_rate.rate = Mock()
        mock_rate.rate.type = "DEFAULT"
        mock_rate.rate.value = 21.0  # Float value
        mock_rate.comment = None

        mock_response = Mock()
        mock_response.vatRateResults = [mock_rate]

        # Mock the SOAP client
        mock_soap_client = Mock()
        mock_soap_client.service.retrieveVatRates.return_value = mock_response
        self.client.client = mock_soap_client

        # Execute
        rate = self.client.get_vat_rate("ES")

        # Verify: Should be Decimal("21"), not Decimal("21.0")
        self.assertEqual(rate, Decimal("21"))
        self.assertEqual(str(rate), "21")  # Ensure string representation is clean
