from django.conf import settings
from django.conf.urls import url, patterns, include
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.core.urlresolvers import reverse_lazy
from django.contrib import admin
from django.views.generic.base import RedirectView, TemplateView


admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    url(r'^$',  TemplateView.as_view(template_name='home.html'), name='home'),
    # url(r'^example/', include('example.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:

    url(r'^admin/', include(admin.site.urls)),
    url(r'^plan/', include('plans.urls')),
    url(r'^accounts/login/$', 'django.contrib.auth.views.login', name="login"),

    url(r'^foo/', include('example.foo.urls')),

)
urlpatterns += staticfiles_urlpatterns()
urlpatterns += patterns('',
    url(r'^media/(?P<path>.*)$', 'django.views.static.serve', {
        'document_root': settings.MEDIA_ROOT,
    }),
)
