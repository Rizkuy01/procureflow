from django.contrib import admin
from .models import (
    ApprovalAction,
    AuditEvent,
    Discrepancy,
    CancellationRequest,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Receipt,
    ReceiptItem,
    ServiceMilestone,
    SupplierEvaluation,
    Supplier,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "department", "managerial_band", "is_active")
    list_filter = ("role", "department", "is_active")
    search_fields = ("user__username", "user__email")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_email", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_name", "contact_email")


@admin.register(SupplierEvaluation)
class SupplierEvaluationAdmin(admin.ModelAdmin):
    list_display = ("request", "supplier", "total_score_display", "evaluator", "evaluated_at")
    list_filter = ("supplier",)
    search_fields = ("request__request_no", "supplier__name", "evaluator__username")

    @admin.display(description="Total score")
    def total_score_display(self, obj):
        return f"{obj.total_score:.2f}"


class PurchaseRequestItemInline(admin.TabularInline):
    model = PurchaseRequestItem
    extra = 0


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("request_no", "title", "department", "requester", "status", "estimated_total")
    list_filter = ("status", "department")
    search_fields = ("request_no", "title", "department", "requester__username")
    readonly_fields = ("request_no", "estimated_total", "created_at", "updated_at")
    inlines = [PurchaseRequestItemInline]


@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    list_display = ("request", "stage", "approver", "decision", "decided_at")
    list_filter = ("stage", "decision")
    search_fields = ("request__request_no", "approver__username")
    readonly_fields = ("decided_at",)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("entity_type", "entity_id", "action", "actor", "created_at")
    list_filter = ("entity_type", "action")
    search_fields = ("entity_type", "entity_id", "action", "actor__username")
    readonly_fields = (
        "actor",
        "entity_type",
        "entity_id",
        "action",
        "summary",
        "old_value",
        "new_value",
        "created_at",
    )


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("po_no", "request", "supplier", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("po_no", "request__request_no", "supplier__name")


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ("purchase_order", "source_request_item", "ordered_quantity", "unit_price")


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("purchase_order", "received_by", "received_at")


@admin.register(ReceiptItem)
class ReceiptItemAdmin(admin.ModelAdmin):
    list_display = ("receipt", "purchase_order_item", "received_quantity")


@admin.register(ServiceMilestone)
class ServiceMilestoneAdmin(admin.ModelAdmin):
    list_display = ("purchase_order", "name", "is_completed", "due_date")
    list_filter = ("is_completed",)


@admin.register(Discrepancy)
class DiscrepancyAdmin(admin.ModelAdmin):
    list_display = ("purchase_order", "status", "resolved_by", "resolved_at")
    list_filter = ("status",)


@admin.register(CancellationRequest)
class CancellationRequestAdmin(admin.ModelAdmin):
    list_display = ("request", "requested_by", "decision", "reviewed_by", "created_at")
    list_filter = ("decision",)
    readonly_fields = ("created_at", "reviewed_at")
