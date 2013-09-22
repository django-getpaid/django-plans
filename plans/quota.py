def get_user_quota(user):
    """
    Tiny helper for getting quota dict for user (left mostly for backward compatibility)
    """
    return user.userplan.plan.get_quota_dict()

