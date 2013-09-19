# Create your views here.
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.views.generic import ListView, CreateView, DeleteView
from .forms import FooForm
from .models import Foo
from plans.quota import get_user_quota


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

    def delete(self, request, *args, **kwargs):
        if not get_user_quota(request.user).get('CAN_DELETE_FOO', True):
            messages.error(request, 'Sorry, your plan does not allow to deletes Foo. Please upgrade!')
            return redirect('foo_del', pk=self.get_object().pk)
        else:
            return super(FooDeleteView, self).delete(request, *args, **kwargs)

