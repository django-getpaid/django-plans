import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.core.cache import cache
from requests.exceptions import ConnectionError, Timeout
from zeep import Client
from zeep.exceptions import Fault, TransportError

logger = logging.getLogger("plans.taxation.tedb")


class TEDBClient:
    """
    Client for European Commission's TEDB SOAP web service.
    Provides real-time VAT rates with caching and fallback mechanisms.
    """

    WSDL_URL = "https://ec.europa.eu/taxation_customs/tedb/ws/VatRetrievalService.wsdl"
    CACHE_TIMEOUT = 3600 * 24  # 24 hours
    CACHE_KEY_PREFIX = "tedb_vat_rate"

    def __init__(self):
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize SOAP client with error handling."""
        try:
            self.client = Client(self.WSDL_URL)
            logger.info("TEDB SOAP client initialized successfully")
        except (ConnectionError, Timeout, TransportError, Fault) as e:
            logger.error(f"Failed to initialize TEDB SOAP client: {e}")
            self.client = None

    def _get_cache_key(self, country_code: str, date: str = None) -> str:
        """Generate cache key for VAT rate."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        return f"{self.CACHE_KEY_PREFIX}_{country_code}_{date}"

    def get_vat_rate(self, country_code: str) -> Optional[Decimal]:
        """
        Retrieve VAT rate for a country from TEDB service.

        Args:
            country_code: ISO 2-letter country code (e.g., 'DE', 'FR')

        Returns:
            Decimal VAT rate or None if not found/error
        """
        date = datetime.now().strftime("%Y-%m-%d")

        # Check cache first
        cache_key = self._get_cache_key(country_code, date)
        cached_rate = cache.get(cache_key)
        if cached_rate is not None:
            logger.debug(f"Retrieved cached VAT rate for {country_code}: {cached_rate}")
            return cached_rate

        # Try TEDB service
        if self.client:
            try:
                logger.info(f"Retrieving VAT rate from TEDB for {country_code}")

                response = self.client.service.retrieveVatRates(
                    memberStates={"isoCode": [country_code]}, situationOn=date
                )

                if hasattr(response, "vatRateResults") and response.vatRateResults:
                    # Look for standard/default VAT rate
                    for vat_rate in response.vatRateResults:
                        if (
                            hasattr(vat_rate, "memberState")
                            and vat_rate.memberState == country_code
                            and hasattr(vat_rate, "rate")
                            and hasattr(vat_rate, "type")
                        ):

                            # Check if this is a standard rate
                            if vat_rate.type == "STANDARD":
                                rate_info = vat_rate.rate
                                # Handle both dict and zeep object formats
                                if hasattr(rate_info, "value") and hasattr(
                                    rate_info, "type"
                                ):
                                    if rate_info.type == "DEFAULT":
                                        # Convert to Decimal and normalize to remove trailing zeros
                                        # This ensures "24.0" becomes "24" for consistent JSON serialization
                                        raw_decimal = Decimal(str(rate_info.value))
                                        rate = (
                                            raw_decimal.quantize(Decimal("1"))
                                            if raw_decimal % 1 == 0
                                            else raw_decimal
                                        )

                                        # Cache the result
                                        cache.set(cache_key, rate, self.CACHE_TIMEOUT)
                                        logger.info(
                                            f"Retrieved standard VAT rate from TEDB for {country_code}: {rate}%"
                                        )
                                        return rate
            except (Fault, TransportError, ConnectionError, Timeout) as e:
                logger.warning(f"TEDB service error for {country_code}: {e}")

        logger.warning(f"Could not retrieve VAT rate from TEDB for {country_code}")
        return None
