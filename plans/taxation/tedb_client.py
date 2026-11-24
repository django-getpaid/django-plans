import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, NamedTuple, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import localdate
from requests.exceptions import RequestException
from zeep import Client, Transport
from zeep.exceptions import Fault, TransportError, XMLSyntaxError

logger = logging.getLogger("plans.taxation.tedb")

# What a TEDB call raises when the service is down, slow or answers garbage
# (HTML error pages, HTTP 5xx from the EU gateway).
TEDB_ERRORS = (RequestException, Fault, TransportError, XMLSyntaxError)


class StandardRate(NamedTuple):
    rate: Decimal
    valid_from: date


def select_standard_rate(vat_rate_results, country_code: str) -> Optional[StandardRate]:
    """The standard VAT rate of ``country_code`` among TEDB ``vatRateResults``.

    TEDB lists regional standard rates next to the mainland one (Spain's
    Canary Islands, Germany's import row), so the STANDARD/DEFAULT row
    without a comment wins; when every row carries a comment (France's only
    row cites its law), the highest rate does.
    """
    rows = [
        row
        for row in vat_rate_results
        if row.memberState == country_code
        and row.type == "STANDARD"
        and row.rate.type == "DEFAULT"
    ]
    if not rows:
        return None
    mainland = [row for row in rows if not row.comment]
    if mainland:
        chosen = mainland[0]
    else:
        chosen = max(rows, key=lambda row: row.rate.value)
        if len(rows) > 1:
            logger.warning(
                f"Multiple regional rates for {country_code}, using highest: {chosen.rate.value}%"
            )
    rate = Decimal(str(chosen.rate.value))
    if rate % 1 == 0:
        rate = rate.quantize(Decimal("1"))
    return StandardRate(rate, chosen.situationOn)


def retrieve_standard_rates(
    soap_client, country_codes: Iterable[str], on: date
) -> dict[str, Optional[StandardRate]]:
    """Standard rate of each country in force on ``on``; raises ``TEDB_ERRORS``."""
    country_codes = list(country_codes)
    response = soap_client.service.retrieveVatRates(
        memberStates={"isoCode": country_codes}, situationOn=on
    )
    results = response.vatRateResults or []
    return {code: select_standard_rate(results, code) for code in country_codes}


class TEDBClient:
    """
    Client for European Commission's TEDB SOAP web service.
    Provides real-time VAT rates with caching and fallback mechanisms.
    """

    WSDL_URL = "https://ec.europa.eu/taxation_customs/tedb/ws/VatRetrievalService.wsdl"
    # A day's rate is fetched the day before (see get_vat_rate), so it must
    # outlive the whole of its own day.
    CACHE_TIMEOUT = 3600 * 24 * 2
    # A failed lookup is not repeated for this long: during an outage every
    # order would otherwise wait PLANS_TEDB_TIMEOUT for each date it asks for.
    RETRY_AFTER = 300
    UNAVAILABLE = "unavailable"
    CACHE_KEY_PREFIX = "tedb_vat_rate"
    DEFAULT_TIMEOUT = 10

    def __init__(self):
        self.client = None
        self._initialize_client()

    @classmethod
    def create_soap_client(cls) -> Client:
        """SOAP client with the WSDL loaded; raises ``TEDB_ERRORS``."""
        timeout = getattr(settings, "PLANS_TEDB_TIMEOUT", cls.DEFAULT_TIMEOUT)
        transport = Transport(timeout=timeout, operation_timeout=timeout)
        return Client(cls.WSDL_URL, transport=transport)

    def _initialize_client(self):
        """Initialize SOAP client with error handling."""
        try:
            self.client = self.create_soap_client()
            logger.info("TEDB SOAP client initialized successfully")
        except TEDB_ERRORS as e:
            logger.error(f"Failed to initialize TEDB SOAP client: {e}")
            self.client = None

    def _get_cache_key(self, country_code: str, date: str = None) -> str:
        """Generate cache key for VAT rate."""
        if not date:
            date = localdate().isoformat()
        return f"{self.CACHE_KEY_PREFIX}_{country_code}_{date}"

    def get_vat_rate(self, country_code: str, on: date = None) -> Optional[Decimal]:
        """
        Standard VAT rate of a country in force on ``on`` (default: today).

        The next day's rate is looked up as well while TEDB answers, so a
        rate change at midnight is already cached when the day starts.

        Returns:
            Decimal VAT rate or None if not found/error
        """
        on = on or localdate()
        rate = self._get_cached_vat_rate(country_code, on)
        if rate is not None:
            self._get_cached_vat_rate(country_code, on + timedelta(days=1))
        return rate

    def _get_cached_vat_rate(self, country_code: str, on: date) -> Optional[Decimal]:
        cache_key = self._get_cache_key(country_code, on.isoformat())
        cached_rate = cache.get(cache_key)
        if cached_rate == self.UNAVAILABLE:
            return None
        if cached_rate is not None:
            logger.debug(f"Retrieved cached VAT rate for {country_code}: {cached_rate}")
            return cached_rate
        if not self.client:
            logger.warning(f"Could not retrieve VAT rate from TEDB for {country_code}")
            return None

        logger.info(f"Retrieving VAT rate from TEDB for {country_code} on {on}")
        try:
            found = retrieve_standard_rates(self.client, [country_code], on)[
                country_code
            ]
        except TEDB_ERRORS as e:
            logger.warning(f"TEDB service error for {country_code}: {e}")
            found = None
        if found is None:
            logger.warning(f"Could not retrieve VAT rate from TEDB for {country_code}")
            cache.set(cache_key, self.UNAVAILABLE, self.RETRY_AFTER)
            return None

        cache.set(cache_key, found.rate, self.CACHE_TIMEOUT)
        logger.info(
            f"Retrieved standard VAT rate from TEDB for {country_code} on {on}: {found.rate}%"
        )
        return found.rate
