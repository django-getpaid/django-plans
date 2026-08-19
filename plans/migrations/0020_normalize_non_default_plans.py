from django.db import migrations


def false_to_null(apps, schema_editor):
    Plan = apps.get_model("plans", "Plan")
    Plan.objects.filter(default=False).update(default=None)


class Migration(migrations.Migration):
    dependencies = [
        ("plans", "0019_order_userplan_plan_before"),
    ]

    operations = [
        # False and NULL both mean "not the default plan" (see the field's
        # help_text), but the unique constraint tolerates only one stored
        # False. At most one row can exist with default=False, so this
        # touches at most one row; reverse is a no-op because NULL already
        # meant the same thing.
        migrations.RunPython(false_to_null, migrations.RunPython.noop),
    ]
