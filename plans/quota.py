def get_user_quota(user):
    """
    Tiny helper for getting quota dict for user
    If user has expired plan, return default plan or None
    """
    from .base.models import AbstractPlan
    Plan = AbstractPlan.get_concrete_model()
    plan = Plan.get_current_plan(user)
    return plan.get_quota_dict()
