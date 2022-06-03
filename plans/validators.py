import six
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.translation import gettext_lazy as _

from plans.importer import import_name
from plans.quota import get_user_quota


class QuotaValidator(object):
    """
    Base class for all Quota validators needed for account activation
    """

    required_to_activate = True
    default_quota_value = None

    @property
    def code(self):
        raise ImproperlyConfigured('Quota code name is not provided for validator')

    def get_quota_value(self, user, quota_dict=None):
        """
        Returns quota value for a given user
        """
        if quota_dict is None:
            quota_dict = get_user_quota(user)

        return quota_dict.get(self.code, self.default_quota_value)

    def get_error_message(self, quota_value, **kwargs):
        return u'Plan validation error'

    def get_error_params(self, quota_value, **kwargs):
        return {
            'quota': quota_value,
            'validator_codename': self.code,
        }

    def __call__(self, user, quota_dict=None, **kwargs):
        """
        Performs validation of quota limit for a user account
        """
        raise NotImplementedError('Please implement specific QuotaValidator')

    def on_activation(self, user, quota_dict=None, **kwargs):
        """
        Hook for any action that validator needs to do while successful activation of the plan
        Most useful for validators not required to activate, e.g. some "option" is turned ON for user
        but when user downgrade plan this option should be turned OFF automatically rather than
        stops account activation
        """
        pass


class ModelCountValidator(QuotaValidator):
    """
    Validator that checks if there is no more than quota number of objects given model
    """

    @property
    def model(self):
        raise ImproperlyConfigured('ModelCountValidator requires model name')

    def get_queryset(self, user):
        return self.model.objects.all()

    def get_error_message(self, quota_value, **kwargs):
        return _('Limit of %(model_name_plural)s exceeded. The limit is %(quota)s items.')

    def get_error_params(self, quota_value, total_count, **kwargs):
        return {
            'quota': quota_value,
            'model_name_plural': self.model._meta.verbose_name_plural.title().lower(),
            'validator_codename': self.code,
            'total_count': total_count,
        }

    def __call__(self, user, quota_dict=None, **kwargs):
        quota = self.get_quota_value(user, quota_dict)
        total_count = self.get_queryset(user).count() + kwargs.get('add', 0)
        if quota is not None and total_count > quota:
            raise ValidationError(message=self.get_error_message(
                quota), params=self.get_error_params(quota, total_count))


class ModelAttributeValidator(ModelCountValidator):
    """
    Validator checks if every obj.attribute value for a given model satisfy condition
    provided in check_attribute_value() method.

    .. warning::
        ModelAttributeValidator requires `get_absolute_url()` method on provided model.
    """

    @property
    def attribute(self):
        raise ImproperlyConfigured('ModelAttributeValidator requires defining attribute name')

    def check_attribute_value(self, attribute_value, quota_value):
        # default is to value is <= limit
        return attribute_value <= quota_value

    def get_error_message(self, quota_value, **kwargs):
        return _('Following %(model_name_plural)s are not in limits: %(objects)s')

    def get_error_params(self, quota_value, total_count, **kwargs):
        return {
            'quota': quota_value,
            'validator_codename': self.code,
            'model_name_plural': self.model._meta.verbose_name_plural.title().lower(),
            'objects': u', '.join(map(lambda o: u'<a href="%s">%s</a>' % (o.get_absolute_url(), six.u(o)),
                                      kwargs['not_valid_objects'])),
        }

    def __call__(self, user, quota_dict=None, **kwargs):
        quota_value = self.get_quota_value(user, quota_dict)
        not_valid_objects = []
        if quota_value is not None:
            for obj in self.get_queryset(user):
                if not self.check_attribute_value(getattr(obj, self.attribute), quota_value):
                    not_valid_objects.append(obj)
        if not_valid_objects:
            raise ValidationError(
                self.get_error_message(quota_value, not_valid_objects=not_valid_objects),
                self.get_error_params(quota_value, not_valid_objects=not_valid_objects),
            )


def plan_validation(user, plan=None, on_activation=False):
    """
    Validates validator that represents quotas in a given system
    :param user:
    :param plan:
    :return:
    """
    if plan is None:
        # if plan is not given, the default is to use current plan of the user
        plan = user.userplan.plan
    quota_dict = plan.get_quota_dict()
    validators = getattr(settings, 'PLANS_VALIDATORS', {})
    validators = import_name(validators)
    errors = {
        'required_to_activate': [],
        'other': [],
    }

    for quota in validators:
        validator = import_name(validators[quota])

        if on_activation:
            validator.on_activation(user, quota_dict)
        else:
            try:
                validator(user, quota_dict)
            except ValidationError as e:
                if validator.required_to_activate:
                    errors['required_to_activate'].extend(e.messages)
                else:
                    errors['other'].extend(e.messages)
    return errors
