# from django.conf import settings
from plans.taxation import TaxationPolicy


class RussianTaxationPolicy(TaxationPolicy):
    """
    FIXME: description needed

    """

#   This could be inherited unless there is a reason to be custom
#    def get_default_tax(self):
#        return getattr(settings, 'PLANS_TAX', None)
#
#    def get_issuer_country_code(self):
#        return getattr(settings, 'PLANS_TAX_COUNTRY', None)

    def get_tax_rate(self, tax_id, country_code):
        # TODO
        return 0
