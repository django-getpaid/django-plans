class UserPlanMiddleware(object):
    def process_request(self, request):
        assert hasattr(request, 'user'), "The UserPlan middleware requires authentication middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.auth.middleware.AuthenticationMiddleware'."

        request.user_plan = request.user.userplan
