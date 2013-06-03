Templates
=========

Account expiration warnings
---------------------------
Via the ``plans.context_processors.account_status`` this module allows
to get information in any template about:

 * user account has expired  - ``{{ ACCOUNT_EXPIRED }}``,
 * user account is not active - ``{{ ACCOUNT_NOT_ACTIVE }}``,
 * user account will expire soon - ``{{ EXPIRE_IN_DAYS }}``,
 * an URL of account extend action - ``{{ EXTEND_URL }}``,
 * an URL of account activate action - ``{{ ACTIVATE_URL }}``.

First you need to add a context processor to your settings, e.g.::


    TEMPLATE_CONTEXT_PROCESSORS = global_settings.TEMPLATE_CONTEXT_PROCESSORS + (
        'plans.context_processors.account_status',
        )

The context processor is defined as follows:

.. autofunction:: plans.context_processors.account_status

What you might want to do now is to create a custom ``expiration_messages.html`` template::


    {% load i18n %}

    {% if ACCOUNT_EXPIRED %}
        <div class="messages_permanent error">
            {% blocktrans with url=EXTEND_URL %}
                Your account has expired. Please <a href="{{ url }}">extend your account</a>.
            {% endblocktrans %}
        </div>
    {% else %}

        {% if ACCOUNT_NOT_ACTIVE %}
            <div class="messages_permanent warning">
            {% blocktrans with url=ACTIVATE_URL %}
                Your account is not active. Possibly you are over some limits.
                Try to <a href="{{ url }}">activate your account</a>.
            {% endblocktrans %}
            </div>
        {% endif %}

        {% if EXPIRE_IN_DAYS >= 0 and EXPIRE_IN_DAYS <= 14 %}
            <div class="messages_permanent warning">
                {% blocktrans with extend_url=EXTEND_URL days_to_expire=EXPIRE_IN_DAYS %}
                    Your account will expire soon (in {{ days_to_expire }} days).
                    We recommend to <a href="{{ extend_url }}">extend your account now.</a>
                {% endblocktrans %}
            </div>
        {% endif %}

    {% endif %}








and put ``{% include "expiration_messages.html" %}`` in suitable places (for example in base template of every user logged pages). Here in template you can customize when exactly you want to display notifications (e.g. how many days before expiration).