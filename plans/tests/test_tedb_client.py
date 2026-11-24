import threading
import time
from datetime import date
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from freezegun import freeze_time
from requests.exceptions import ConnectionError, HTTPError
from zeep.exceptions import XMLSyntaxError

from plans.taxation.tedb_client import (
    StandardRate,
    TEDBClient,
    select_standard_rate,
)


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

    def test_cache_key_default_date_is_the_local_day(self):
        # 05:30 UTC on 1 January is still 31 December in Chicago (TIME_ZONE)
        with freeze_time("2026-01-01 05:30:00"):
            key = self.client._get_cache_key("DE")
        self.assertEqual(key, "tedb_vat_rate_DE_2025-12-31")

    def test_get_vat_rate_from_cache(self):
        """Today's and tomorrow's cached rates need no TEDB request."""
        cache.set(self.client._get_cache_key("DE", "2025-11-01"), Decimal("19"))
        cache.set(self.client._get_cache_key("DE", "2025-11-02"), Decimal("19"))
        self.client.client = Mock()

        rate = self.client.get_vat_rate("DE", date(2025, 11, 1))

        self.assertEqual(rate, Decimal("19"))
        self.client.client.service.retrieveVatRates.assert_not_called()

    def test_get_vat_rate_no_client(self):
        """Test VAT rate retrieval when SOAP client is not available."""
        self.client.client = None

        rate = self.client.get_vat_rate("DE")

        self.assertIsNone(rate)

    def test_rate_is_asked_for_the_given_day(self):
        self.client.client = tedb_soap(vat_row("FI", 25.5))

        rate = self.client.get_vat_rate("FI", date(2024, 9, 1))

        self.assertEqual(rate, Decimal("25.5"))
        self.assertEqual(
            self.client.client.service.retrieveVatRates.call_args_list[0],
            call(memberStates={"isoCode": ["FI"]}, situationOn=date(2024, 9, 1)),
        )

    def test_default_day_is_the_local_day(self):
        self.client.client = tedb_soap(vat_row("FI", 25.5))

        with freeze_time("2026-01-01 05:30:00"):
            self.client.get_vat_rate("FI")

        self.assertEqual(
            situation_days(self.client.client),
            [date(2025, 12, 31), date(2026, 1, 1)],
        )

    def test_tomorrows_rate_is_cached_before_tomorrow(self):
        """A change at midnight does not need TEDB to answer at midnight."""
        new_year = date(2027, 1, 1)
        finland = {
            True: vat_row("FI", 26, situation_on=new_year),
            False: vat_row("FI", 25.5),
        }
        soap = Mock()
        soap.service.retrieveVatRates.side_effect = lambda **request: SimpleNamespace(
            vatRateResults=[finland[request["situationOn"] >= new_year]]
        )
        self.client.client = soap

        self.assertEqual(
            self.client.get_vat_rate("FI", date(2026, 12, 31)), Decimal("25.5")
        )
        soap.service.retrieveVatRates.side_effect = HTTPError("504 Gateway Time-out")

        self.assertEqual(self.client.get_vat_rate("FI", new_year), Decimal("26"))

    def test_http_error_returns_none_and_is_not_retried_at_once(self):
        soap = Mock()
        soap.service.retrieveVatRates.side_effect = HTTPError("504 Gateway Time-out")
        self.client.client = soap

        self.assertIsNone(self.client.get_vat_rate("DE", date(2025, 11, 1)))
        self.assertIsNone(self.client.get_vat_rate("DE", date(2025, 11, 1)))

        self.assertEqual(situation_days(soap), [date(2025, 11, 1)])

    def test_failed_lookup_is_retried_after_retry_after(self):
        soap = Mock()
        soap.service.retrieveVatRates.side_effect = HTTPError("504 Gateway Time-out")
        self.client.client = soap
        with freeze_time("2025-11-01 12:00:00") as frozen:
            self.client.get_vat_rate("DE")
            soap.service.retrieveVatRates.side_effect = None
            soap.service.retrieveVatRates.return_value = SimpleNamespace(
                vatRateResults=[vat_row("DE", 19)]
            )
            frozen.tick(TEDBClient.RETRY_AFTER + 1)

            self.assertEqual(self.client.get_vat_rate("DE"), Decimal("19"))

    def test_failing_tomorrow_lookup_keeps_todays_rate_and_is_not_repeated(self):
        cache.set(self.client._get_cache_key("DE", "2025-11-01"), Decimal("19"))
        soap = Mock()
        soap.service.retrieveVatRates.side_effect = HTTPError("504 Gateway Time-out")
        self.client.client = soap

        for _ in range(2):
            self.assertEqual(
                self.client.get_vat_rate("DE", date(2025, 11, 1)), Decimal("19")
            )

        self.assertEqual(situation_days(soap), [date(2025, 11, 2)])

    def test_missing_standard_rate_returns_none(self):
        self.client.client = tedb_soap(vat_row("DE", 7, type="REDUCED"))

        self.assertIsNone(self.client.get_vat_rate("DE", date(2025, 11, 1)))

    def test_regional_rate_filtering_spain(self):
        """
        Test that regional rates are filtered correctly (Spain case).

        Spain has 2 STANDARD+DEFAULT rates in TEDB:
        - 7% for Canary Islands (with comment)
        - 21% for mainland (no comment)

        This test verifies we return 21% (mainland), not 7% (regional).
        """
        self.client.client = tedb_soap(
            vat_row("ES", 7.0, comment="VAT - Canary Islands - "),
            vat_row("ES", 21.0),
        )

        rate = self.client.get_vat_rate("ES", date(2025, 11, 1))

        # Verify: Should return 21 (mainland), not 7 (Canary Islands)
        self.assertEqual(rate, Decimal("21"))

        # Verify the rate was cached
        cached = cache.get(self.client._get_cache_key("ES", "2025-11-01"))
        self.assertEqual(cached, Decimal("21"))

    def test_all_rates_have_comments_use_highest(self):
        """
        Test fallback when all rates have comments (e.g., France).

        When all STANDARD+DEFAULT rates have comments, we should use the highest.
        """
        self.client.client = tedb_soap(
            vat_row("FR", 20.0, comment="Article 278 of the General Tax Code")
        )

        rate = self.client.get_vat_rate("FR", date(2025, 11, 1))

        # Verify: Should return 20 (the only/highest rate)
        self.assertEqual(rate, Decimal("20"))

    def test_highest_of_several_commented_rates(self):
        rows = [
            vat_row("PT", 16, comment="Azores"),
            vat_row("PT", 23, comment="Mainland, Art. 18"),
            vat_row("PT", 22, comment="Madeira"),
        ]

        self.assertEqual(
            select_standard_rate(rows, "PT"),
            StandardRate(Decimal("23"), date(2025, 1, 1)),
        )

    def test_decimal_normalization(self):
        """Test that whole number rates are normalized (21.0 → 21)."""
        self.client.client = tedb_soap(vat_row("ES", 21.0))

        rate = self.client.get_vat_rate("ES", date(2025, 11, 1))

        # Verify: Should be Decimal("21"), not Decimal("21.0")
        self.assertEqual(rate, Decimal("21"))
        self.assertEqual(str(rate), "21")  # Ensure string representation is clean


def vat_row(
    state,
    value,
    comment=None,
    type="STANDARD",
    rate_type="DEFAULT",
    situation_on=date(2025, 1, 1),
):
    """One entry of TEDB's ``vatRateResults``."""
    return SimpleNamespace(
        memberState=state,
        type=type,
        rate=SimpleNamespace(type=rate_type, value=value),
        comment=comment,
        situationOn=situation_on,
    )


def tedb_soap(*rows):
    """A zeep client whose TEDB answers ``rows`` to every request."""
    soap = Mock()
    soap.service.retrieveVatRates.return_value = SimpleNamespace(
        vatRateResults=list(rows)
    )
    return soap


def situation_days(soap):
    return [
        request.kwargs["situationOn"]
        for request in soap.service.retrieveVatRates.call_args_list
    ]


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
