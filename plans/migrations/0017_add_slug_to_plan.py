# Generated manually on 2024-12-01 for adding slug field to Plan model

from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    """Populate slug field from existing name values"""
    Plan = apps.get_model("plans", "Plan")
    used_slugs = set()

    for plan in Plan.objects.all():
        if not plan.slug:
            base_slug = slugify(plan.name)
            # Handle empty slugs from whitespace-only names
            if not base_slug:
                base_slug = f"plan-{plan.pk}"

            slug = base_slug
            counter = 1

            # Handle duplicates by appending a number
            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1

            plan.slug = slug
            used_slugs.add(slug)
            plan.save()


def reverse_populate_slugs(apps, schema_editor):
    """Reverse migration - clear slug field"""
    Plan = apps.get_model("plans", "Plan")
    Plan.objects.update(slug="")


class Migration(migrations.Migration):

    dependencies = [
        ("plans", "0016_invoice_cancellation_reason_invoice_credit_note_for_and_more"),
    ]

    operations = [
        # Add slug field as nullable CharField first
        migrations.AddField(
            model_name="plan",
            name="slug",
            field=models.CharField(max_length=100, null=True, verbose_name="slug"),
        ),
        # Populate slugs from existing names
        migrations.RunPython(populate_slugs, reverse_populate_slugs),
        # Convert to required SlugField with unique constraint
        # WARNING: This operation creates a unique index synchronously and can
        # LOCK THE TABLE on PostgreSQL with large datasets, causing downtime.
        # For production PostgreSQL deployments, consider:
        # 1. Run: python manage.py migrate plans 0017 --fake
        # 2. Manually: CREATE UNIQUE INDEX CONCURRENTLY plans_plan_slug_unique ON plans_plan (slug);
        # 3. Then: ALTER TABLE plans_plan ADD CONSTRAINT plans_plan_slug_unique UNIQUE USING INDEX plans_plan_slug_unique;
        migrations.AlterField(
            model_name="plan",
            name="slug",
            field=models.SlugField(max_length=100, unique=True, verbose_name="slug"),
        ),
    ]
