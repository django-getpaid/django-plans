from django.contrib import admin

from .models import Foo, Company, Profile


admin.site.register(Profile)
admin.site.register(Company)
admin.site.register(Foo)
