import logging
from decimal import Decimal
from urllib.error import URLError
from xml.sax import SAXParseException

import stdnum.eu.vat
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.utils.html import format_html
from requests.exceptions import ConnectionError
from suds import WebFault
from suds.transport import TransportError

from plans.taxation import TaxationPolicy
from plans.utils import country_code_transform

logger = logging.getLogger('plans.taxation.eu.vies')


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
    """

    # Standard VAT rates according to
    # http://ec.europa.eu/taxation_customs/resources/documents/taxation/vat/how_vat_works/rates/vat_rates_en.pdf
    # Situation at 1 Jan 2017

    EU_COUNTRIES_VAT = {
        'BE': Decimal('21'),  # Belgium
        'BG': Decimal('20'),  # Bulgaria
        'CZ': Decimal('21'),  # Czech Republic
        'DK': Decimal('25'),  # Denmark
        'DE': Decimal('19'),  # Germany
        'EE': Decimal('20'),  # Estonia
        'EL': Decimal('24'),  # Greece
        'ES': Decimal('21'),  # Spain
        'FR': Decimal('20'),  # France
        'HR': Decimal('25'),  # Croatia
        'IE': Decimal('23'),  # Ireland
        'IT': Decimal('22'),  # Italy
        'CY': Decimal('19'),  # Cyprus
        'LV': Decimal('21'),  # Latvia
        'LT': Decimal('21'),  # Lithuania
        'LU': Decimal('17'),  # Luxembourg
        'HU': Decimal('27'),  # Hungary
        'MT': Decimal('18'),  # Malta
        'NL': Decimal('21'),  # Netherlands
        'AT': Decimal('20'),  # Austria
        'PL': Decimal('23'),  # Poland
        'PT': Decimal('23'),  # Portugal
        'RO': Decimal('19'),  # Romania
        'SI': Decimal('22'),  # Slovenia
        'SK': Decimal('20'),  # Slovakia
        'FI': Decimal('24'),  # Finland
        'SE': Decimal('25'),  # Sweden
        # 'GB': Decimal('20'),  # United Kingdom (Great Britain)
    }

    @classmethod
    def is_in_EU(cls, country_code):
        return country_code_transform(country_code).upper() in cls.EU_COUNTRIES_VAT

    @classmethod
    def get_default_tax(cls):
        issuer_country_code = cls.get_issuer_country_code()
        issuer_country_code = country_code_transform(issuer_country_code)
        try:
            return cls.EU_COUNTRIES_VAT[issuer_country_code]
        except KeyError:
            raise ImproperlyConfigured("EUTaxationPolicy requires that issuer country is in EU")

    @classmethod
    def get_tax_rate(cls, tax_id, country_code, request=None):
        """
        returns tax rate and if the request was successful.
        """
        country_code = country_code_transform(country_code)
        issuer_country_code = cls.get_issuer_country_code()
        if not cls.is_in_EU(issuer_country_code):
            raise ImproperlyConfigured("EUTaxationPolicy requires that issuer country is in EU")

        if not tax_id and not country_code:
            # No vat id, no country
            return cls.get_default_tax(), True

        elif not tax_id and country_code:
            # Customer is not a company, we know his country

            if cls.is_in_EU(country_code):
                # Customer (private person) is from a EU
                # Customer pays his VAT rate
                return cls.EU_COUNTRIES_VAT[country_code], True
            else:
                # Customer (private person) not from EU
                # VAT n/a
                return None, True

        else:
            # Customer is company, we now country and vat id

            if country_code.upper() == issuer_country_code.upper():
                # Company is from the same country as issuer
                # Normal tax
                return cls.get_default_tax(), True

            if cls.is_in_EU(country_code):
                # Company is from other EU country
                try:
                    vies_result = bool(stdnum.eu.vat.check_vies(tax_id)['valid'])
                    logger.info("TAX_ID=%s RESULT=%s" % (tax_id, vies_result))
                    if tax_id and vies_result:
                        # Company is registered in VIES
                        # Charge back
                        return None, True
                    else:
                        return cls.EU_COUNTRIES_VAT[country_code], True
                except (
                    WebFault, TransportError, stdnum.exceptions.InvalidComponent, ConnectionError, URLError,
                    SAXParseException,
                ) as e:
                    # If we could not connect to VIES or the VAT ID is incorrect
                    if request:
                        messages.warning(
                            request,
                            format_html(
                                'There was an error during determining validity of your VAT ID.<br/>'
                                'If you think, you have european VAT ID and should not be taxed, '
                                'please try resaving billing info later.<br/>'
                                '<br/>'
                                'European VAT Information Exchange System throw following error: {}',
                                e,
                            )
                        )
                    logger.exception("TAX_ID=%s" % (tax_id))
                    return cls.EU_COUNTRIES_VAT[country_code], False
            else:
                # Company is not from EU
                # VAT n/a
                return None, True
