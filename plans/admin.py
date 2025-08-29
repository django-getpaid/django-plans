from copy import deepcopy

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from ordered_model.admin import OrderedModelAdmin

from .forms import PartialCreditNoteForm

from plans.base.models import (
    AbstractBillingInfo,
    AbstractInvoice,
    AbstractOrder,
    AbstractPlan,
    AbstractPlanPricing,
    AbstractPlanQuota,
    AbstractPricing,
    AbstractQuota,
    AbstractRecurringUserPlan,
    AbstractUserPlan,
)

from .signals import account_automatic_renewal

Invoice = AbstractInvoice.get_concrete_model()
UserPlan = AbstractUserPlan.get_concrete_model()
Plan = AbstractPlan.get_concrete_model()
PlanQuota = AbstractPlanQuota.get_concrete_model()
Quota = AbstractQuota.get_concrete_model()
PlanPricing = AbstractPlanPricing.get_concrete_model()
Pricing = AbstractPricing.get_concrete_model()
RecurringUserPlan = AbstractRecurringUserPlan.get_concrete_model()
Order = AbstractOrder.get_concrete_model()
BillingInfo = AbstractBillingInfo.get_concrete_model()


class UserLinkMixin(object):
    def user_link(self, obj):
        user_model = get_user_model()
        app_label = user_model._meta.app_label
        model_name = user_model._meta.model_name
        change_url = reverse(
            "admin:%s_%s_change" % (app_label, model_name), args=(obj.user.id,)
        )
        return format_html('<a href="{}">{}</a>', change_url, obj.user.username)

    user_link.short_description = "User"
    user_link.allow_tags = True


class PlanQuotaInline(admin.TabularInline):
    model = PlanQuota


class PlanPricingInline(admin.TabularInline):
    model = PlanPricing


class QuotaAdmin(OrderedModelAdmin):
    list_display = [
        "codename",
        "name",
        "description",
        "unit",
        "is_boolean",
        "move_up_down_links",
    ]

    readonly_fields = ("created", "updated_at")
    list_display_links = list_display


def copy_plan(modeladmin, request, queryset):
    """
    Admin command for duplicating plans preserving quotas and pricings.
    """
    for plan in queryset:
        plan_copy = deepcopy(plan)
        plan_copy.id = None
        plan_copy.available = False
        plan_copy.default = False
        plan_copy.created = None
        plan_copy.save(force_insert=True)

        for pricing in plan.planpricing_set.all():
            pricing.id = None
            pricing.plan = plan_copy
            pricing.save(force_insert=True)

        for quota in plan.planquota_set.all():
            quota.id = None
            quota.plan = plan_copy
            quota.save(force_insert=True)


copy_plan.short_description = _("Make a plan copy")


class PlanAdmin(OrderedModelAdmin):
    search_fields = (
        "name",
        "customized__username",
        "customized__email",
    )
    list_filter = ("available", "visible")
    list_display = [
        "name",
        "description",
        "customized",
        "default",
        "available",
        "is_free",
        "created",
        "move_up_down_links",
    ]
    list_display_links = list_display
    inlines = (PlanPricingInline, PlanQuotaInline)
    list_select_related = True
    raw_id_fields = ("customized",)
    readonly_fields = ("created", "updated_at")
    actions = [
        copy_plan,
    ]

    def queryset(self, request):
        return super(PlanAdmin, self).queryset(request).select_related("customized")


class BillingInfoAdmin(UserLinkMixin, admin.ModelAdmin):
    search_fields = ("user__username", "user__email", "tax_number", "name")
    list_display = (
        "user",
        "tax_number",
        "name",
        "street",
        "zipcode",
        "city",
        "country",
    )
    list_display_links = list_display
    list_select_related = True
    readonly_fields = ("user_link", "created", "updated_at")
    exclude = ("user",)


def make_order_completed(modeladmin, request, queryset):
    for order in queryset:
        order.complete_order()


make_order_completed.short_description = _("Make selected orders completed")


def make_order_returned(modeladmin, request, queryset):
    for order in queryset:
        order.return_order()


make_order_returned.short_description = _("Make selected orders returned")


def make_order_invoice(modeladmin, request, queryset):
    for order in queryset:
        if (
            Invoice.objects.filter(
                type=Invoice.INVOICE_TYPES["INVOICE"], order=order
            ).count()
            == 0
        ):
            Invoice.create(order, Invoice.INVOICE_TYPES["INVOICE"])


make_order_invoice.short_description = _("Make invoices for orders")


class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    raw_id_fields = ("user",)


class OrderAdmin(admin.ModelAdmin):
    list_filter = ("status", "created", "completed", "plan__name", "pricing")
    raw_id_fields = ("user",)
    search_fields = ("id", "user__username", "user__email", "invoice__full_number")
    list_display = (
        "id",
        "name",
        "created",
        "user",
        "status",
        "completed",
        "tax",
        "amount",
        "currency",
        "plan",
        "pricing",
        "plan_extended_from",
        "plan_extended_until",
    )
    readonly_fields = ("created", "updated_at")
    list_display_links = list_display
    actions = [make_order_completed, make_order_returned, make_order_invoice]
    inlines = (InvoiceInline,)

    def queryset(self, request):
        return (
            super(OrderAdmin, self)
            .queryset(request)
            .select_related("plan", "pricing", "user")
        )


def cancel_selected_invoices(modeladmin, request, queryset):
    for invoice in queryset:
        try:
            invoice.cancel_invoice()
            modeladmin.message_user(
                request, f"Invoice {invoice.full_number} cancelled successfully."
            )
        except Exception as e:
            modeladmin.message_user(
                request, f"Could not cancel {invoice.full_number}: {e}", level="ERROR"
            )


cancel_selected_invoices.short_description = _("Cancel and issue credit note")


def create_partial_credit_note(modeladmin, request, queryset):
    """Create partial credit notes with custom amounts"""
    if queryset.count() != 1:
        modeladmin.message_user(
            request,
            "Please select exactly one invoice to create a partial credit note.",
            level="ERROR",
        )
        return

    invoice = queryset.first()
    if invoice.type != invoice.INVOICE_TYPES.INVOICE:
        modeladmin.message_user(
            request,
            "Only regular invoices can have partial credit notes.",
            level="ERROR",
        )
        return

    if request.method == "POST" and "apply" in request.POST:
        form = PartialCreditNoteForm(request.POST)
        if form.is_valid():
            credit_note = invoice.create_partial_credit_note(
                form.cleaned_data["net_amount"],
                form.cleaned_data["tax_amount"],
                form.cleaned_data["reason"],
            )
            modeladmin.message_user(
                request,
                "Partial credit note %s created successfully for invoice %s."
                % (credit_note.full_number, invoice.full_number),
            )
            return HttpResponseRedirect(reverse("admin:plans_invoice_changelist"))
    else:
        # Initialize form with default values from invoice
        initial_data = {
            "net_amount": invoice.total_net,
            "tax_amount": invoice.tax_total,
            "reason": "",
        }
        form = PartialCreditNoteForm(initial=initial_data)

    context = {
        "title": "Create Partial Credit Note for Invoice %s" % invoice.full_number,
        "invoice": invoice,
        "opts": modeladmin.model._meta,
        "has_view_permission": modeladmin.has_view_permission(request),
        "form": form,
    }

    return TemplateResponse(
        request, "admin/plans/invoice/partial_credit_note_form.html", context
    )


create_partial_credit_note.short_description = _("Create partial credit note")


class InvoiceAdmin(admin.ModelAdmin):
    search_fields = ("full_number", "buyer_tax_number", "user__username", "user__email")
    list_filter = (
        "type",
        "issued",
        "tax",
        "currency",
        "buyer_country",
    )
    list_display = (
        "full_number",
        "issued",
        "total_net",
        "currency",
        "user",
        "tax",
        "buyer_name",
        "buyer_city",
        "buyer_tax_number",
    )
    readonly_fields = (
        "created",
        "updated_at",
        "full_number",
        "number",
        "total_net",
        "tax_total",
        "total",
    )
    list_display_links = list_display
    list_select_related = True
    raw_id_fields = ("user", "order", "credit_note_for")
    actions = (cancel_selected_invoices, create_partial_credit_note)
    fieldsets = (
        (
            _("Invoice Details"),
            {
                "fields": (
                    "type",
                    "full_number",
                    "number",
                    "user",
                    "order",
                    "credit_note_for",
                    "cancellation_reason",
                )
            },
        ),
        (
            _("Dates"),
            {
                "fields": (
                    "issued",
                    "selling_date",
                    "payment_date",
                    "issued_duplicate",
                    "created",
                    "updated_at",
                )
            },
        ),
        (
            _("Billing Details"),
            {
                "fields": (
                    "item_description",
                    "quantity",
                    "unit_price_net",
                    "tax",
                    "rebate",
                    "currency",
                    "total_net",
                    "tax_total",
                    "total",
                )
            },
        ),
        (
            _("Buyer Details"),
            {
                "fields": (
                    "buyer_name",
                    "buyer_street",
                    "buyer_zipcode",
                    "buyer_city",
                    "buyer_country",
                    "buyer_tax_number",
                )
            },
        ),
        (
            _("Shipping Details"),
            {
                "fields": (
                    "require_shipment",
                    "shipping_name",
                    "shipping_street",
                    "shipping_zipcode",
                    "shipping_city",
                    "shipping_country",
                )
            },
        ),
        (
            _("Issuer Details"),
            {
                "fields": (
                    "issuer_name",
                    "issuer_street",
                    "issuer_zipcode",
                    "issuer_city",
                    "issuer_country",
                    "issuer_tax_number",
                )
            },
        ),
    )


class RecurringPlanInline(admin.StackedInline):
    model = RecurringUserPlan
    readonly_fields = ("created", "updated_at")
    extra = 0


def autorenew_payment(modeladmin, request, queryset):
    """
    Automatically renew payment for this plan
    """
    for user_plan in queryset:
        account_automatic_renewal.send(sender=None, user=user_plan.user)


autorenew_payment.short_description = _("Autorenew plan")


class UserPlanAdmin(UserLinkMixin, admin.ModelAdmin):
    list_filter = (
        "active",
        "expire",
        "plan__name",
        "plan__available",
        "plan__visible",
        "recurring__renewal_triggered_by",
        "recurring__payment_provider",
        "recurring__token_verified",
        "recurring__pricing",
    )
    search_fields = ("user__username", "user__email", "plan__name", "recurring__token")
    list_display = (
        "user",
        "plan",
        "expire",
        "active",
        "recurring__renewal_triggered_by",
        "recurring__token_verified",
        "recurring__payment_provider",
        "recurring__pricing",
    )
    list_display_links = list_display
    list_select_related = True
    readonly_fields = ("user_link", "created", "updated_at")
    inlines = (RecurringPlanInline,)
    actions = [
        autorenew_payment,
    ]
    fields = ("user", "user_link", "plan", "expire", "active", "created", "updated_at")
    raw_id_fields = [
        "user",
        "plan",
    ]

    def recurring__renewal_triggered_by(self, obj):
        return obj.recurring.renewal_triggered_by

    recurring__renewal_triggered_by.admin_order_field = (
        "recurring__renewal_triggered_by"
    )
    recurring__renewal_triggered_by.short_description = "Renewal triggered by"

    def recurring__token_verified(self, obj):
        return obj.recurring.token_verified

    recurring__token_verified.admin_order_field = "recurring__token_verified"
    recurring__token_verified.boolean = True
    recurring__token_verified.short_description = "Renewal token verified"

    def recurring__payment_provider(self, obj):
        return obj.recurring.payment_provider

    recurring__payment_provider.admin_order_field = "recurring__payment_provider"
    recurring__payment_provider.short_description = "Renewal payment_provider"

    def recurring__pricing(self, obj):
        return obj.recurring.pricing

    recurring__pricing.admin_order_field = "recurring__pricing"


admin.site.register(Quota, QuotaAdmin)
admin.site.register(Plan, PlanAdmin)
admin.site.register(UserPlan, UserPlanAdmin)
admin.site.register(Pricing)
admin.site.register(Order, OrderAdmin)
admin.site.register(BillingInfo, BillingInfoAdmin)
admin.site.register(Invoice, InvoiceAdmin)
