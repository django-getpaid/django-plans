from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("plans", "0019_order_userplan_plan_before"),
    ]

    operations = [
        migrations.AddField(
            model_name="recurringuserplan",
            name="last_renewal_slot_open",
            field=models.DateField(
                blank=True,
                help_text=(
                    "Local calendar date on which the last attempted renewal "
                    "slot opened. A schedule entry fires only when its own "
                    "opening date is strictly newer -- an ordering on whole "
                    "days, deliberately free of timestamp arithmetic, which "
                    "cannot be made consistent across time zones and database "
                    "backends."
                ),
                null=True,
                verbose_name="last renewal slot opened on",
            ),
        ),
    ]
