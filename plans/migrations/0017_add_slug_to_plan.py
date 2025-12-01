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
        # NOTE: For PostgreSQL production deployments with large tables,
        # consider running this migration with --fake and manually creating
        # the unique index with CREATE UNIQUE INDEX CONCURRENTLY
        migrations.AlterField(
            model_name="plan",
            name="slug",
            field=models.SlugField(max_length=100, unique=True, verbose_name="slug"),
        ),
    ]
