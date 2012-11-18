from django.conf import settings

class TaxationPolicy(object):
    """
    Abstract class for defining taxation policies.
    Taxation policy is a way to handle what tax rate should be put on the order, this depends
    on user billing data.

    Custom taxation policy should implement only method ``get_tax_rate()``. This method should
    return a percent value of tax that should be added to the Order, or None if tax is not applicable.
    """

    def get_default_tax(self):
        return getattr(settings, 'TAX', None)

    def get_issuer_country_code(self):
        return getattr(settings, 'TAX_COUNTRY', None)

    def get_tax_rate(self, vat_id, country_code):
        raise NotImplementedError('Method get_tax_rate should be implemented.')

