from django.db import models
from django.urls import reverse


class Foo(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    name = models.CharField(max_length=100, default="A new foo")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("foo_del", args=(self.pk,))
