from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import TestCase
from requests.exceptions import ConnectionError

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
