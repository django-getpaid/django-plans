from django.conf.urls import url, patterns

from django.contrib.auth.decorators import login_required

from example.foo.views import FooListView, FooCreateView, FooDeleteView


urlpatterns = patterns(
    '',
    url(r'^list/$', login_required(FooListView.as_view()), name='foo_list'),
    url(r'^add/$', login_required(FooCreateView.as_view()), name='foo_add'),
    url(r'^del/(?P<pk>\d+)/$', login_required(FooDeleteView.as_view()), name='foo_del'),
)

