from django.contrib.auth.decorators import login_required
from django.urls import path

from .views import FooCreateView, FooDeleteView, FooListView

urlpatterns = [
    path('list/', login_required(FooListView.as_view()), name='foo_list'),
    path('add/', login_required(FooCreateView.as_view()), name='foo_add'),
    path('del/<int:pk>/', login_required(FooDeleteView.as_view()), name='foo_del'),
]
