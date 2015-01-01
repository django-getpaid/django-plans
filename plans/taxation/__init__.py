from django.conf import settings

class TaxationPolicy(object):
    """
    Abstract class for defining taxation policies.
    Taxation policy is a way to handle what tax rate should be put on the order, this depends
    on user billing data.

    Custom taxation policy should implement only method ``get_default_tax(vat_id, country_code)``.
    This method should return a percent value of tax that should be added to the Order,
    or None if tax is not applicable.
    """

    @classmethod
    def get_default_tax(cls):
        """
        Gets default tax rate. Simply returns ``settings.PLANS_TAX``

        :return: Decimal()
        """
        return getattr(settings, 'PLANS_TAX', None)

    @classmethod
    def get_issuer_country_code(cls):
        """
        Gets issuers country. Simply returns ``settings.PLANS_TAX_COUNTRY``

        :return: unicode
        """
        return getattr(settings, 'PLANS_TAX_COUNTRY', None)

    @classmethod
    def get_tax_rate(cls, tax_id, country_code):
        """
        Methods

        :param tax_id: customer tax id
        :param country_code:  customer country in ISO 2-letters format
        :return: Decimal()
        """
        raise NotImplementedError('Method get_tax_rate should be implemented.')

