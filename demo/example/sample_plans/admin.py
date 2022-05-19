# This import is required for importing admin class from plans.admin
import plans.admin  # noqa
from django.contrib import admin

from .models import TestApp


@admin.register(TestApp)
class TestAppAdmin(admin.ModelAdmin):
    pass
