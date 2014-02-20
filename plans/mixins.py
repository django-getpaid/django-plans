from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View


class LoginRequired(View):
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginRequired, self).dispatch(*args, **kwargs)


class UserObjectsOnlyMixin(object):
    def get_queryset(self):
        return super(UserObjectsOnlyMixin, self).get_queryset().filter(user=self.request.user)