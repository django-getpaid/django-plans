from __future__ import unicode_literals

from django.db import models


class Foo(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    name = models.CharField(max_length=100, default="A new foo")

    def __str__(self):
        return self.name
