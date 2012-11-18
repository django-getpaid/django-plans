from django.conf import settings
from plans.taxation import TaxationPolicy


class RussianTaxationPolicy(TaxationPolicy):
    """
    Abstract class for defining taxation policies.
    Taxation policy is a way to handle what tax rate should put on the order, this depends
    on user billing data.
    """

    def get_default_tax(self):
        return getattr(settings, 'TAX', None)

    def get_issuer_country_code(self):
        return getattr(settings, 'TAX_COUNTRY', None)

    def get_tax_rate(self, tax_id, country_code):
        # TODO
        return 0
