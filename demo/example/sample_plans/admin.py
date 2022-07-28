# This import is required for importing admin class from plans.admin
from django.contrib import admin

import plans.admin  # noqa

from .models import TestApp


@admin.register(TestApp)
class TestAppAdmin(admin.ModelAdmin):
    pass
