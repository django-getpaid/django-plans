from django.conf.urls import url, patterns, include
from django.core.urlresolvers import reverse_lazy
from django.contrib import admin
from django.views.generic.base import RedirectView


admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    url(r'^$',  RedirectView.as_view(url=reverse_lazy('current_plan')), name='home'),
    # url(r'^example/', include('example.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:

    url(r'^admin/', include(admin.site.urls)),
    url(r'^plan/', include('plans.urls')),
    url(r'^accounts/login/$', 'django.contrib.auth.views.login', name="login"),
)
