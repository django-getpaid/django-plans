from django.conf import settings
from django.core.exceptions import ValidationError
from plans.importer import import_name
from plans.quota import get_user_quota

class QuotaValidator(object):
    """
    Base class for all Quota validators needed for account activation
    """
    code = ''

    def get_quota(self, user):
        quotas = get_user_quota(user)
        return quotas.get(self.code, None)




def account_full_validation(user):
    """
    Validates validator that represents quotas in a given system
    :param user:
    :return:
    """
    quotas = get_user_quota(user)
    validators = getattr(settings, 'PLAN_ACTIVATION_VALIDATORS', {})
    errors = []
    for quota in quotas:
        if validators.has_key(quota):
            validator = import_name(validators[quota])
            try:
                validator(user)
            except ValidationError, e:
                errors.append(e)
    return errors