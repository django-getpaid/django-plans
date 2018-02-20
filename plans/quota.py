from plans.contrib import get_buyer_for_user


def get_buyer_quota(buyer):
    return buyer.buyerplan.plan.get_quota_dict()


def get_user_quota(user):
    """
    Tiny helper for getting quota dict for user (left mostly for backward compatibility)
    """
    buyer = get_buyer_for_user(user)
    return get_buyer_quota(buyer)
