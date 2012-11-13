# Create your views here.
from django.core.urlresolvers import reverse
from django.views.generic import ListView, CreateView, DeleteView
from example.foo.forms import FooForm
from example.foo.models import Foo

class FooListView(ListView):
    model = Foo

    def get_queryset(self):
        return super(FooListView, self).get_queryset().filter(user=self.request.user)


class FooCreateView(CreateView):
    model = Foo
    form_class = FooForm

    def get_initial(self):
        initial = super(FooCreateView, self).get_initial()
        initial['user'] = self.request.user
        return initial

    def get_success_url(self):
        return reverse('foo_list')

    def get_queryset(self):
        return super(FooCreateView, self).get_queryset().filter(user=self.request.user)


class FooDeleteView(DeleteView):
    model = Foo

    def get_queryset(self):
        return super(FooDeleteView, self).get_queryset().filter(user=self.request.user)

    def get_success_url(self):
        return reverse('foo_list')
