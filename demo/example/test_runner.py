from django.test.runner import DiscoverRunner


class PlansTestRunner(DiscoverRunner):
    """
    Run tests for plans module by default for convenience.

    Thanks to this, running

        python manage.py test

    will run plans.tests.* tests, an equivalent of

        python manage.py test plans

    which makes it easier for developers to run correct tests without
    duplicating anything.
    """

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        # If no test labels specified, default to plans module
        # for convenience and least surprise for developers
        if not test_labels:
            test_labels = ["plans"]

        return super().build_suite(
            test_labels=test_labels, extra_tests=extra_tests, **kwargs
        )
