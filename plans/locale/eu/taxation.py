from django.core.exceptions import ImproperlyConfigured
from suds import WebFault
from suds.transport import TransportError
import vatnumber

from plans.taxation import TaxationPolicy

class EUTaxationPolicy(TaxationPolicy):
    """
    This taxation policy should be correct for all EU countries. It uses following rules:
        * if issuer country is not in EU - assert error,
        * return **default tax** in cases:
            * if issuer country and customer country are the same,
            * if issuer country and customer country are **not** not the same, but customer is private person from EU,
            * if issuer country and customer country are **not** not the same, customer is company, but his tax ID is **not** valid according VIES system.
        * return tax not applicable (``None``) in cases:
            * if issuer country and customer country are **not** not the same, customer is company from EU and his tax id is valid according VIES system.
            * if issuer country and customer country are **not** not the same and customer is private person **not** from EU,
            * if issuer country and customer country are **not** not the same and customer is company **not** from EU.


    Please note, that term "private person" refers in system to user that did not provide tax ID and
    ``company`` refers to user that provides it.

    """
    EU_COUNTRIES = {
        'AT', # Austria
        'BE', # Belgium
        'BG', # Bulgaria
        'CY', # Cyprus
        'CZ', # Czech Republic
        'DK', # Denmark
        'EE', # Estonia
        'FI', # Finland
        'FR', # France
        'DE', # Germany
        'GR', # Greece
        'HU', # Hungary
        'IE', # Ireland
        'IT', # Italy
        'LV', # Latvia
        'LT', # Lithuania
        'LU', # Luxembourg
        'MT', # Malta
        'NL', # Netherlands
        'PL', # Poland
        'PT', # Portugal
        'RO', # Romania
        'SK', # Slovakia
        'SI', # Slovenia
        'ES', # Spain
        'SE', # Sweden
        'GB', # United Kingdom (Great Britain)
    }

    @classmethod
    def is_in_EU(cls, country_code):
        return country_code.upper() in cls.EU_COUNTRIES


    @classmethod
    def get_tax_rate(cls, tax_id, country_code):
        issuer_country = cls.get_issuer_country_code()
        if not cls.is_in_EU(issuer_country):
            raise ImproperlyConfigured("EUTaxationPolicy requires that issuer country is in EU")

        if not tax_id and not country_code:
            # No vat id, no country
            return cls.get_default_tax()

        elif tax_id and not country_code:
            # Customer is not a company, we know his country

           if cls.is_in_EU(country_code):
               # Customer (private person) is from a EU
               # He must pay full VAT of our country
               return cls.get_default_tax()
           else:
               # Customer (private person) not from EU
               # charge back
               return None

        else:
            # Customer is company, we now country and vat id

            if country_code.upper() == issuer_country.upper():
               # Company is from the same country as issuer
               # Normal tax
               return cls.get_default_tax()
            if cls.is_in_EU(country_code):
                # Company is from other EU country
                try:
                    if tax_id and vatnumber.check_vies(tax_id):
                    # Company is registered in VIES
                    # Charge back
                        return None
                    else:
                        return cls.get_default_tax()
                except (WebFault, TransportError):
                    # If we could not connect to VIES
                    return cls.get_default_tax()
            else:
                # Company is not from EU
                # Charge back
                return None

