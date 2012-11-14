import suds
import vatnumber

from django.conf import settings

from plans.taxation import TaxationPolicy

class EUTaxationPolicy(TaxationPolicy):
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

    def is_in_EU(self, country_code):
        return country_code.upper() in self.EU_COUNTRIES

    def get_tax_rate(self, vat_id, country_code):
        issuer_country = self.get_issuer_country_code()
        if not self.is_in_EU(issuer_country):
            raise ImproperlyConfigured("EUTaxationPolicy requires that issuer country is in EU")

        if not vat_id and not country_code:
            # No vat id, no country
            return self.get_default_tax()

        elif vat_id and not country_code:
            # Customer is not a company, we know his country

           if self.is_in_EU(country_code):
               # Customer (private person) is from a EU
               # He must pay full VAT of our country
               return self.get_default_tax()
           else:
               # Customer (private person) not from EU
               # charge back
               return None

        else:
            # Customer is company, we now country and vat id

            if country_code.upper() == issuer_country.upper():
               # Company is from the same country as issuer
               # Normal tax
               return self.get_default_tax()
            if self.is_in_EU(country_code):
                # Company is from other EU country
                try:
                    if vat_id and vatnumber.check_vies(vat_id):
                    # Company is registered in VIES
                    # Charge back
                        return None
                    else:
                        return self.get_default_tax()
                except suds.WebFault:
                    # If we could not connect to VIES
                    return self.get_default_tax()
            else:
                # Company is not from EU
                # Charge back
                return None

