from .models import Foo
from plans.validators import ModelCountValidator
from plans.contrib import get_buyer_for_user


class MaxFoosValidator(ModelCountValidator):
    code = 'MAX_FOO_COUNT'
    model = Foo

    def get_queryset(self, buyer):
        queryset = super(MaxFoosValidator, self).get_queryset(buyer)
        return queryset.filter(company=buyer)


max_foos_validator = MaxFoosValidator()
