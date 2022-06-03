from django.contrib import admin
from django.contrib.auth import views
from django.urls import include, path
from django.views.generic.base import TemplateView

admin.autodiscover()

urlpatterns = [
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('admin/', admin.site.urls),
    path('plan/', include('plans.urls')),
    path('accounts/login/', views.LoginView.as_view(), name="login"),
    path('accounts/logout/', views.LogoutView.as_view(), {'next_page': '/'}, name="logout"),
    path('foo/', include('example.foo.urls')),
]
