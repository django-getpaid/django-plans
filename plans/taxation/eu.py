import logging
import time
from urllib.error import URLError
from xml.sax import SAXParseException

import stdnum.eu.vat
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.utils.html import format_html
from django.utils.timezone import localdate
from requests.exceptions import ConnectionError
from zeep.exceptions import Fault, TransportError, XMLSyntaxError

from plans.taxation import TaxationPolicy
from plans.taxation.eu_vat_rates import (
    EU_STANDARD_VAT_RATES,
    latest_standard_vat_rates,
    standard_vat_rate,
)
from plans.taxation.tedb_client import TEDBClient
from plans.utils import country_code_transform

logger = logging.getLogger("plans.taxation.eu.vies")


class EUTaxationPolicy(TaxationPolicy):
    """
    This taxation policy should be correct for all EU countries. It uses following rules:
        * if issuer country is not in EU - assert error,
        * for buyer of the same country as issuer - return issuer tax,
        * for company buyer from EU (with VIES) returns VAT n/a reverse charge,
        * for non-company buyer from EU returns VAT from buyer country,
        * for non-EU buyer return VAT n/a.

    This taxation policy was updated at 1 Jan 2015 after new UE VAT regulations. You should also probably
    register in MOSS system.

    VAT rates are retrieved from the European Commission's TEDB service when possible,
    with fallback to static rates table for reliability.
    """

    # Latest rate of each member state; the rate on a given day comes from
    # plans.taxation.eu_vat_rates.standard_vat_rate.
    EU_COUNTRIES_VAT = latest_standard_vat_rates()

    @classmethod
    def is_in_EU(cls, country_code):
        return country_code_transform(country_code).upper() in cls.EU_COUNTRIES_VAT

    @classmethod
    def _get_tedb_client(cls):
        """Get TEDB client instance, cached as class attribute."""
        if not hasattr(cls, "_tedb_client"):
            cls._tedb_client = TEDBClient()
        return cls._tedb_client

    @classmethod
    def _get_vat_rate_from_tedb(cls, country_code, on=None):
        """
        Standard VAT rate in force on ``on`` (default: today) from TEDB, with
        fallback to the static rate history.

        Args:
            country_code: ISO 2-letter country code
            on: the day the tax arises

        Returns:
            Decimal VAT rate or None if not available
        """
        on = on or localdate()
        rate = cls._get_tedb_client().get_vat_rate(country_code, on)
        if rate is not None:
            logger.info(f"Using TEDB VAT rate for {country_code}: {rate}")
            return rate

        if country_code not in EU_STANDARD_VAT_RATES:
            logger.error(f"No VAT rate available for {country_code}")
            return None
        rate = standard_vat_rate(country_code, on)
        logger.info(f"Using fallback VAT rate for {country_code} on {on}: {rate}")
        return rate

    @classmethod
    def _get_vat_rate(cls, country_code, on):
        """``_get_vat_rate_from_tedb``, never None for an EU country (overrides may return None)."""
        rate = cls._get_vat_rate_from_tedb(country_code, on)
        if rate is not None:
            return rate
        return standard_vat_rate(country_code, on)

    @classmethod
    def get_default_tax(cls, on=None):
        issuer_country_code = cls.get_issuer_country_code()
        issuer_country_code = country_code_transform(issuer_country_code)

        # Try TEDB first, then fallback to static table
        rate = cls._get_vat_rate_from_tedb(issuer_country_code, on)
        if rate is not None:
            return rate

        raise ImproperlyConfigured(
            "EUTaxationPolicy requires that issuer country is in EU"
        )

    # Seconds-scale VIES throttling/outage codes worth retrying; anything
    # else (e.g. INVALID_INPUT) is deterministic and retries are useless.
    VIES_TRANSIENT_FAULTS = (
        "MS_MAX_CONCURRENT_REQ",
        "GLOBAL_MAX_CONCURRENT_REQ",
        "MS_UNAVAILABLE",
        "SERVICE_UNAVAILABLE",
        "TIMEOUT",
    )
    VIES_RETRY_ATTEMPTS = 3
    VIES_RETRY_DELAY = 2  # seconds, doubled after each attempt

    @classmethod
    def validate_vies(cls, tax_id):
        """Live VIES registry check with backoff on transient faults.

        Renewal batches fire many checks in a short window and trip the
        member states' concurrency limits; those faults clear in seconds.
        Overridable to plug in a cached/stored validation source.
        """
        for attempt in range(cls.VIES_RETRY_ATTEMPTS):
            try:
                return bool(stdnum.eu.vat.check_vies(tax_id)["valid"])
            except Fault as fault:
                transient = any(
                    code in str(fault) for code in cls.VIES_TRANSIENT_FAULTS
                )
                if not transient or attempt == cls.VIES_RETRY_ATTEMPTS - 1:
                    raise
                delay = cls.VIES_RETRY_DELAY * 2**attempt
                logger.warning(
                    "Transient VIES fault for TAX_ID=%s (attempt %s/%s), "
                    "retrying in %ss: %s",
                    tax_id,
                    attempt + 1,
                    cls.VIES_RETRY_ATTEMPTS,
                    delay,
                    fault,
                )
                time.sleep(delay)

    @classmethod
    def get_tax_rate(cls, tax_id, country_code, request=None, on=None):
        """
        returns tax rate and if the request was successful.

        ``on`` is the day the tax arises (default: today), e.g. the day a
        prepayment is received.
        """
        on = on or localdate()
        if country_code:
            country_code = country_code_transform(country_code.upper())
        issuer_country_code = cls.get_issuer_country_code()
        if not cls.is_in_EU(issuer_country_code):
            raise ImproperlyConfigured(
                "EUTaxationPolicy requires that issuer country is in EU"
            )

        if not tax_id and not country_code:
            # No vat id, no country
            return cls.get_default_tax(on), True

        elif not tax_id and country_code:
            # Customer is not a company, we know his country

            if cls.is_in_EU(country_code):
                # Customer (private person) is from a EU
                # Customer pays his VAT rate
                return cls._get_vat_rate(country_code, on), True
            else:
                # Customer (private person) not from EU
                # VAT n/a
                return None, True

        else:
            # Customer is company, we now country and vat id

            if country_code.upper() == issuer_country_code.upper():
                # Company is from the same country as issuer
                # Normal tax
                return cls.get_default_tax(on), True

            if cls.is_in_EU(country_code):
                # Company is from other EU country
                try:
                    vies_result = cls.validate_vies(tax_id)
                    logger.info("TAX_ID=%s RESULT=%s" % (tax_id, vies_result))
                    if tax_id and vies_result:
                        # Company is registered in VIES
                        # Charge back
                        return None, True
                    else:
                        return cls._get_vat_rate(country_code, on), True
                except (
                    Fault,
                    TransportError,
                    XMLSyntaxError,
                    stdnum.exceptions.InvalidComponent,
                    ConnectionError,
                    URLError,
                    SAXParseException,
                    TimeoutError,
                ) as e:
                    # If we could not connect to VIES or the VAT ID is incorrect
                    if request:
                        messages.warning(
                            request,
                            format_html(
                                "There was an error during determining validity of your VAT ID.<br/>"
                                "If you think, you have european VAT ID and should not be taxed, "
                                "please try resaving billing info later.<br/>"
                                "<br/>"
                                "European VAT Information Exchange System throw following error: {}",
                                e,
                            ),
                        )
                    logger.exception("TAX_ID=%s" % (tax_id))
                    return cls._get_vat_rate(country_code, on), False
            else:
                # Company is not from EU
                # VAT n/a
                return None, True
