from fabric.api import local, task


@task
def freeze_fixtures():
    local(
        'python manage.py dumpdata auth.User plans.BillingInfo plans.Invoice '
        'plans.Order plans.Plan plans.Pricing plans.PlanPricing plans.Quota '
        'plans.PlanQuota plans.UserPlan > example/foo/fixtures/initial_data.json',
    )
