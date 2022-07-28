from plans.validators import ModelCountValidator

from .models import Foo


class MaxFoosValidator(ModelCountValidator):
    code = 'MAX_FOO_COUNT'
    model = Foo

    def get_queryset(self, user):
        return super(MaxFoosValidator, self).get_queryset(user).filter(user=user)


max_foos_validator = MaxFoosValidator()
