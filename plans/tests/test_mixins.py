from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.views.generic import ListView
from model_bakery import baker

from plans.base.models import AbstractOrder
from plans.mixins import UserObjectsOnlyMixin

User = get_user_model()
Order = AbstractOrder.get_concrete_model()


class UserOrderList(UserObjectsOnlyMixin, ListView):
    model = Order


class UserObjectsOnlyMixinTests(TestCase):
    def test_only_the_requesting_users_objects_are_listed(self):
        user = baker.make(User)
        own_order = baker.make("Order", user=user)
        baker.make("Order", user=baker.make(User))
        request = RequestFactory().get("/")
        request.user = user
        view = UserOrderList()
        view.setup(request)

        self.assertEqual(list(view.get_queryset()), [own_order])
