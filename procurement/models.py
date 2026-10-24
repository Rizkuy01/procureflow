from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid


class UserProfile(models.Model):
    class Role(models.TextChoices):
        REQUESTER = "requester", "Requester"
        SECTION_HEAD = "section_head", "Section Head"
        FINANCE = "finance", "Finance"
        ADMIN_PROCUREMENT = "admin_procurement", "Admin Procurement"
        PROCUREMENT = "procurement", "Procurement"
        MANAGERIAL_APPROVER = "managerial_approver", "Managerial Approver"
        RECEIVER = "receiver", "Receiver"
        ADMIN_SYSTEM = "admin_system", "Admin System"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="procurement_profile",
    )
    role = models.CharField(max_length=32, choices=Role.choices)
    managerial_band = models.CharField(
        max_length=1,
        choices=(("X", "Pak X"), ("Y", "Pak Y"), ("Z", "Pak Z")),
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SupplierEvaluation(models.Model):
    request = models.ForeignKey(
        "PurchaseRequest", on_delete=models.CASCADE, related_name="supplier_evaluations"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="evaluations"
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="supplier_evaluations"
    )
    price_score = models.DecimalField(max_digits=5, decimal_places=2)
    quality_score = models.DecimalField(max_digits=5, decimal_places=2)
    lead_time_score = models.DecimalField(max_digits=5, decimal_places=2)
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.TextField(blank=True)
    evaluated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("request", "supplier"),
                name="unique_supplier_evaluation_per_request",
            ),
        ]
        ordering = ["-evaluated_at", "supplier__name"]

    @property
    def total_score(self):
        scores = tuple(
            Decimal(str(getattr(self, field)))
            for field in (
                "price_score",
                "quality_score",
                "lead_time_score",
                "compliance_score",
            )
        )
        return sum(scores) / 4

    def clean(self):
        super().clean()
        for field in (
            "price_score",
            "quality_score",
            "lead_time_score",
            "compliance_score",
        ):
            score = getattr(self, field)
            if score is not None and not 0 <= Decimal(str(score)) <= 100:
                raise ValidationError({field: "Score harus berada di antara 0 dan 100."})


def generate_request_number():
    return f"REQ-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


class PurchaseRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_SECTION_HEAD = "pending_section_head", "Pending Section Head"
        PENDING_FINANCE = "pending_finance", "Pending Finance"
        PENDING_ADMIN_PROCUREMENT = (
            "pending_admin_procurement",
            "Pending Admin Procurement",
        )
        RETURNED_FOR_CORRECTION = "returned_for_correction", "Returned for Correction"
        PENDING_SUPPLIER_EVALUATION = (
            "pending_supplier_evaluation",
            "Pending Supplier Evaluation",
        )
        PENDING_MANAGERIAL_APPROVAL = (
            "pending_managerial_approval",
            "Pending Managerial Approval",
        )
        CANCELLATION_PENDING = "cancellation_pending", "Cancellation Pending"
        REJECTED = "rejected", "Rejected"
        APPROVED = "approved", "Approved / PO Created"
        PARTIALLY_RECEIVED = "partially_received", "Partially Received"
        DISCREPANCY_OPEN = "discrepancy_open", "Discrepancy Open"
        FULFILLED = "fulfilled", "Fulfilled / Closed"
        CANCELLED = "cancelled", "Cancelled"

    request_no = models.CharField(
        max_length=24, unique=True, default=generate_request_number, editable=False
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_requests",
    )
    title = models.CharField(max_length=200)
    purpose = models.TextField()
    needed_by = models.DateField()
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    proposed_supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="proposed_requests",
        null=True,
        blank=True,
    )
    final_supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="final_requests",
        null=True,
        blank=True,
    )
    estimated_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    previous_status = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.request_no} - {self.title}"

    def calculate_total(self):
        return sum(
            (item.line_total for item in self.items.all()),
            start=self.estimated_total.__class__("0"),
        )

    def refresh_total(self, *, save=True):
        self.estimated_total = self.calculate_total()
        if save:
            self.save(update_fields=["estimated_total", "updated_at"])
        return self.estimated_total


class PurchaseRequestItem(models.Model):
    class ItemType(models.TextChoices):
        GOODS = "goods", "Goods"
        SERVICE = "service", "Service"

    request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    description = models.CharField(max_length=300)
    item_type = models.CharField(max_length=10, choices=ItemType.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit = models.CharField(max_length=50)
    estimated_unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    proposed_supplier_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Rekomendasi Supplier",
        help_text="Nama supplier yang direkomendasikan untuk item ini (opsional)",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="request_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_unit_price__gte=0),
                name="request_item_price_non_negative",
            ),
        ]

    @property
    def line_total(self):
        return self.quantity * self.estimated_unit_price

    def clean(self):
        super().clean()
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than zero."})
        if (
            self.estimated_unit_price is not None
            and self.estimated_unit_price < 0
        ):
            raise ValidationError(
                {"estimated_unit_price": "Estimated price cannot be negative."}
            )

    def __str__(self):
        return self.description


class ApprovalAction(models.Model):
    class Stage(models.TextChoices):
        SECTION_HEAD = "section_head", "Section Head"
        FINANCE = "finance", "Finance"
        ADMIN_PROCUREMENT = "admin_procurement", "Admin Procurement"
        PROCUREMENT = "procurement", "Procurement"
        MANAGERIAL = "managerial", "Managerial"

    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", "Returned for Correction"

    request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="approval_actions",
    )
    stage = models.CharField(max_length=24, choices=Stage.choices)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approval_actions",
    )
    decision = models.CharField(max_length=16, choices=Decision.choices)
    comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["decided_at", "id"]


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=64)
    action = models.CharField(max_length=80)
    summary = models.TextField(blank=True)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


def generate_po_number():
    return f"PO-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PARTIALLY_RECEIVED = "partially_received", "Partially Received"
        FULFILLED = "fulfilled", "Fulfilled"

    po_no = models.CharField(max_length=24, unique=True, default=generate_po_number, editable=False)
    request = models.OneToOneField(PurchaseRequest, on_delete=models.PROTECT, related_name="purchase_order")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.po_no


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    source_request_item = models.OneToOneField(
        PurchaseRequestItem, on_delete=models.PROTECT, related_name="purchase_order_item"
    )
    ordered_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)

    @property
    def received_quantity(self):
        from django.db.models import Sum
        return self.receipt_items.aggregate(total=Sum("received_quantity"))["total"] or Decimal("0")

    @property
    def remaining_quantity(self):
        return self.ordered_quantity - self.received_quantity

    @property
    def line_total(self):
        return self.ordered_quantity * self.unit_price


class Receipt(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="receipts")
    received_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)


class ReceiptItem(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="items")
    purchase_order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name="receipt_items")
    received_quantity = models.DecimalField(max_digits=12, decimal_places=2)

    def clean(self):
        super().clean()
        if self.received_quantity is not None and self.received_quantity <= 0:
            raise ValidationError({"received_quantity": "Received quantity must be greater than zero."})


class ServiceMilestone(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(max_length=200)
    due_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)


class Discrepancy(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="discrepancies")
    receipt = models.ForeignKey(Receipt, on_delete=models.PROTECT, related_name="discrepancies", null=True, blank=True)
    description = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="resolved_discrepancies", null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)


class CancellationRequest(models.Model):
    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    request = models.ForeignKey(
        PurchaseRequest, on_delete=models.CASCADE, related_name="cancellation_requests"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cancellation_requests"
    )
    reason = models.TextField()
    decision = models.CharField(max_length=12, choices=Decision.choices, default=Decision.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="reviewed_cancellations", null=True, blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    previous_status = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)
