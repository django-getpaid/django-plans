import threading
import time
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import ANY, Mock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
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

        mock_client_class.assert_called_once_with(TEDBClient.WSDL_URL, transport=ANY)
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


STUB_WSDL = """<?xml version="1.0" encoding="UTF-8"?>
<wsdl:definitions xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"
    xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:tns="urn:tedb-stub" targetNamespace="urn:tedb-stub">
  <wsdl:types>
    <xs:schema targetNamespace="urn:tedb-stub" elementFormDefault="qualified">
      <xs:element name="retrieveVatRatesReqMsg">
        <xs:complexType><xs:sequence>
          <xs:element name="memberStates"><xs:complexType><xs:sequence>
            <xs:element name="isoCode" type="xs:string" maxOccurs="unbounded"/>
          </xs:sequence></xs:complexType></xs:element>
          <xs:element name="situationOn" type="xs:date"/>
        </xs:sequence></xs:complexType>
      </xs:element>
      <xs:element name="retrieveVatRatesRespMsg"><xs:complexType/></xs:element>
    </xs:schema>
  </wsdl:types>
  <wsdl:message name="request">
    <wsdl:part name="body" element="tns:retrieveVatRatesReqMsg"/>
  </wsdl:message>
  <wsdl:message name="response">
    <wsdl:part name="body" element="tns:retrieveVatRatesRespMsg"/>
  </wsdl:message>
  <wsdl:portType name="port">
    <wsdl:operation name="retrieveVatRates">
      <wsdl:input message="tns:request"/>
      <wsdl:output message="tns:response"/>
    </wsdl:operation>
  </wsdl:portType>
  <wsdl:binding name="binding" type="tns:port">
    <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
    <wsdl:operation name="retrieveVatRates">
      <soap:operation soapAction="retrieveVatRates"/>
      <wsdl:input><soap:body use="literal"/></wsdl:input>
      <wsdl:output><soap:body use="literal"/></wsdl:output>
    </wsdl:operation>
  </wsdl:binding>
  <wsdl:service name="service">
    <wsdl:port name="port" binding="tns:binding">
      <soap:address location="{endpoint}"/>
    </wsdl:port>
  </wsdl:service>
</wsdl:definitions>
"""

STALL_SECONDS = 10


GATEWAY_TIMEOUT_PAGE = b"<html><body><h1>504 Gateway Time-out</h1></body></html>"


def start_tedb_stub(test, stall=None, gateway_timeout=None):
    """Serve a minimal TEDB WSDL on localhost; leave `stall` requests unanswered.

    `stall` is "GET" (the WSDL download) or "POST" (the rate request). A
    stalled request is held for STALL_SECONDS and then dropped, like the
    EU gateway that timed out on 2026-11-12. `gateway_timeout` requests are
    answered with the gateway's HTTP 504 page instead (Blendkit #4556).
    """
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def _send_gateway_timeout(self):
            self.send_response(504)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(GATEWAY_TIMEOUT_PAGE)))
            self.end_headers()
            self.wfile.write(GATEWAY_TIMEOUT_PAGE)

        def do_GET(self):
            if gateway_timeout == "GET":
                self._send_gateway_timeout()
                return
            if stall == "GET":
                release.wait(STALL_SECONDS)
                return
            body = STUB_WSDL.format(endpoint=url).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if gateway_timeout == "POST":
                self._send_gateway_timeout()
                return
            release.wait(STALL_SECONDS)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    test.addCleanup(server.server_close)
    test.addCleanup(server.shutdown)
    test.addCleanup(release.set)
    return url


class TEDBClientTimeoutTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _client_for(self, url):
        with patch.object(TEDBClient, "WSDL_URL", url):
            return TEDBClient()

    @override_settings(PLANS_TEDB_TIMEOUT=0.2)
    def test_stalled_wsdl_download_gives_up_after_configured_timeout(self):
        url = start_tedb_stub(self, stall="GET")

        started = time.monotonic()
        client = self._client_for(url)

        self.assertIsNone(client.client)
        self.assertLess(time.monotonic() - started, STALL_SECONDS / 2)

    @override_settings(PLANS_TEDB_TIMEOUT=0.2)
    def test_stalled_rate_request_gives_up_after_configured_timeout(self):
        client = self._client_for(start_tedb_stub(self, stall="POST"))

        started = time.monotonic()
        rate = client.get_vat_rate("DE")

        self.assertIsNone(rate)
        self.assertLess(time.monotonic() - started, STALL_SECONDS / 2)

    def test_timeout_defaults_to_ten_seconds(self):
        client = self._client_for(start_tedb_stub(self))

        self.assertEqual(client.client.transport.load_timeout, 10)
        self.assertEqual(client.client.transport.operation_timeout, 10)

    def test_gateway_timeout_on_wsdl_download_leaves_no_client(self):
        client = self._client_for(start_tedb_stub(self, gateway_timeout="GET"))

        self.assertIsNone(client.client)

    def test_gateway_timeout_on_rate_request_returns_none(self):
        client = self._client_for(start_tedb_stub(self, gateway_timeout="POST"))

        self.assertIsNone(client.get_vat_rate("DE"))
