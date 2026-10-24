from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    ApprovalAction,
    AuditEvent,
    CancellationRequest,
    Discrepancy,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    Receipt,
    ReceiptItem,
    ServiceMilestone,
    SupplierEvaluation,
    UserProfile,
)


APPROVAL_ROLES = {
    ApprovalAction.Stage.SECTION_HEAD: UserProfile.Role.SECTION_HEAD,
    ApprovalAction.Stage.FINANCE: UserProfile.Role.FINANCE,
    ApprovalAction.Stage.ADMIN_PROCUREMENT: UserProfile.Role.ADMIN_PROCUREMENT,
    ApprovalAction.Stage.PROCUREMENT: UserProfile.Role.PROCUREMENT,
    ApprovalAction.Stage.MANAGERIAL: UserProfile.Role.MANAGERIAL_APPROVER,
}


def managerial_approver_for(total):
    total = Decimal(total)
    if total <= Decimal("1000000"):
        return "Pak X"
    if total <= Decimal("10000000"):
        return "Pak Y"
    return "Pak Z"


def _audit(actor, request, action, old_status, new_status, summary):
    AuditEvent.objects.create(
        actor=actor,
        entity_type="PurchaseRequest",
        entity_id=str(request.pk),
        action=action,
        summary=summary,
        old_value={"status": old_status},
        new_value={"status": new_status},
    )


@transaction.atomic
def submit_request(request_obj, actor):
    if request_obj.requester_id != actor.id:
        raise ValidationError("Hanya requester pemilik request yang dapat submit.")
    if request_obj.status not in (
        PurchaseRequest.Status.DRAFT,
        PurchaseRequest.Status.RETURNED_FOR_CORRECTION,
    ):
        raise ValidationError("Request tidak berada pada status yang dapat disubmit.")
    if not request_obj.items.exists():
        raise ValidationError("Request harus memiliki minimal satu item.")
    request_obj.refresh_total(save=False)
    if request_obj.estimated_total < 0:
        raise ValidationError("Total request tidak valid.")
    old_status = request_obj.status
    request_obj.status = PurchaseRequest.Status.PENDING_SECTION_HEAD
    request_obj.save(update_fields=["estimated_total", "status", "updated_at"])
    _audit(actor, request_obj, "submitted", old_status, request_obj.status, "Request diajukan.")


@transaction.atomic
def reset_approval_after_change(
    request_obj, actor, *, previous_total, previous_supplier_id
):
    if request_obj.requester_id != actor.id:
        raise ValidationError("Hanya requester pemilik request yang dapat mengubah request.")
    if hasattr(request_obj, "purchase_order"):
        raise ValidationError("Request tidak dapat diubah setelah PO dibuat.")
    if request_obj.status in (
        PurchaseRequest.Status.CANCELLATION_PENDING,
        PurchaseRequest.Status.CANCELLED,
        PurchaseRequest.Status.REJECTED,
        PurchaseRequest.Status.FULFILLED,
    ):
        raise ValidationError("Request tidak berada pada status yang dapat diubah.")

    total_changed = Decimal(str(previous_total)) != Decimal(
        str(request_obj.estimated_total)
    )
    supplier_changed = previous_supplier_id != request_obj.proposed_supplier_id
    if not total_changed and not supplier_changed:
        return False

    old_status = request_obj.status
    SupplierEvaluation.objects.filter(request=request_obj).delete()
    request_obj.final_supplier = None
    request_obj.status = PurchaseRequest.Status.PENDING_SECTION_HEAD
    request_obj.save(update_fields=["final_supplier", "status", "updated_at"])
    changes = []
    if total_changed:
        changes.append("nominal berubah")
    if supplier_changed:
        changes.append("supplier usulan berubah")
    _audit(
        actor,
        request_obj,
        "approval_reset",
        old_status,
        request_obj.status,
        f"Approval diulang karena {' dan '.join(changes)}.",
    )
    return True


@transaction.atomic
def decide_request(request_obj, actor, stage, decision, comment=""):
    expected_role = APPROVAL_ROLES.get(stage)
    profile = getattr(actor, "procurement_profile", None)
    if expected_role is None or profile is None or profile.role != expected_role:
        raise ValidationError("Role tidak berwenang untuk tahap approval ini.")
    if stage == ApprovalAction.Stage.MANAGERIAL:
        required_band = managerial_approver_for(request_obj.estimated_total)[-1]
        if profile.managerial_band != required_band:
            raise ValidationError("Approver manajerial tidak sesuai nominal request.")

    transitions = {
        ApprovalAction.Stage.SECTION_HEAD: PurchaseRequest.Status.PENDING_SECTION_HEAD,
        ApprovalAction.Stage.FINANCE: PurchaseRequest.Status.PENDING_FINANCE,
        ApprovalAction.Stage.ADMIN_PROCUREMENT: PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT,
        ApprovalAction.Stage.PROCUREMENT: PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION,
        ApprovalAction.Stage.MANAGERIAL: PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL,
    }
    if request_obj.status != transitions[stage]:
        raise ValidationError("Request belum berada pada tahap approval ini.")
    if stage == ApprovalAction.Stage.ADMIN_PROCUREMENT and decision == ApprovalAction.Decision.REJECTED:
        raise ValidationError("Admin Procurement hanya dapat mengembalikan untuk koreksi.")

    next_status = {
        (ApprovalAction.Stage.SECTION_HEAD, ApprovalAction.Decision.APPROVED): PurchaseRequest.Status.PENDING_FINANCE,
        (ApprovalAction.Stage.FINANCE, ApprovalAction.Decision.APPROVED): PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT,
        (ApprovalAction.Stage.ADMIN_PROCUREMENT, ApprovalAction.Decision.APPROVED): PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION,
        (ApprovalAction.Stage.MANAGERIAL, ApprovalAction.Decision.APPROVED): PurchaseRequest.Status.APPROVED,
    }.get((stage, decision), PurchaseRequest.Status.REJECTED)
    if decision == ApprovalAction.Decision.RETURNED:
        next_status = PurchaseRequest.Status.RETURNED_FOR_CORRECTION

    old_status = request_obj.status
    ApprovalAction.objects.create(
        request=request_obj,
        stage=stage,
        approver=actor,
        decision=decision,
        comment=comment,
    )
    request_obj.status = next_status
    request_obj.save(update_fields=["status", "updated_at"])
    _audit(actor, request_obj, "approval_decision", old_status, next_status, comment)


@transaction.atomic
def select_final_supplier(request_obj, actor, supplier):
    profile = getattr(actor, "procurement_profile", None)
    if profile is None or profile.role != UserProfile.Role.PROCUREMENT:
        raise ValidationError("Hanya Procurement yang dapat menetapkan supplier final.")
    if request_obj.status != PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION:
        raise ValidationError("Request belum berada pada tahap evaluasi supplier.")
    if not supplier.is_active:
        raise ValidationError("Supplier final harus aktif.")
    if not SupplierEvaluation.objects.filter(
        request=request_obj, supplier=supplier
    ).exists():
        raise ValidationError("Supplier harus dievaluasi sebelum ditetapkan sebagai final.")
    old_status = request_obj.status
    request_obj.final_supplier = supplier
    request_obj.status = PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL
    request_obj.save(update_fields=["final_supplier", "status", "updated_at"])
    _audit(actor, request_obj, "supplier_selected", old_status, request_obj.status, supplier.name)


@transaction.atomic
def save_supplier_evaluation(request_obj, actor, data):
    profile = getattr(actor, "procurement_profile", None)
    if profile is None or profile.role != UserProfile.Role.PROCUREMENT:
        raise ValidationError("Hanya Procurement yang dapat mengevaluasi supplier.")
    if request_obj.status != PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION:
        raise ValidationError("Request belum berada pada tahap evaluasi supplier.")
    evaluation = SupplierEvaluation.objects.update_or_create(
        request=request_obj,
        supplier=data["supplier"],
        defaults={
            "evaluator": actor,
            "price_score": data["price_score"],
            "quality_score": data["quality_score"],
            "lead_time_score": data["lead_time_score"],
            "compliance_score": data["compliance_score"],
            "notes": data.get("notes", ""),
        },
    )[0]
    _audit(
        actor, request_obj, "supplier_evaluated", request_obj.status,
        request_obj.status, f"{evaluation.supplier.name}: {evaluation.total_score:.2f}",
    )
    return evaluation


@transaction.atomic
def create_purchase_order(request_obj, actor):
    profile = getattr(actor, "procurement_profile", None)
    if profile is None or profile.role != UserProfile.Role.PROCUREMENT:
        raise ValidationError("Hanya Procurement yang dapat membuat PO.")
    if request_obj.status != PurchaseRequest.Status.APPROVED:
        raise ValidationError("PO hanya dapat dibuat setelah approval managerial.")
    if not request_obj.final_supplier:
        raise ValidationError("Supplier final wajib ditetapkan sebelum membuat PO.")
    if not request_obj.items.exists():
        raise ValidationError("Request harus memiliki item.")
    if hasattr(request_obj, "purchase_order"):
        return request_obj.purchase_order
    po = PurchaseOrder.objects.create(request=request_obj, supplier=request_obj.final_supplier)
    for item in request_obj.items.all():
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            source_request_item=item,
            ordered_quantity=item.quantity,
            unit_price=item.estimated_unit_price,
        )
        if item.item_type == item.ItemType.SERVICE:
            ServiceMilestone.objects.create(
                purchase_order=po,
                name=item.description,
            )
    _audit(actor, request_obj, "po_created", request_obj.status, request_obj.status, po.po_no)
    return po


@transaction.atomic
def record_receipt(po, actor, quantities, notes=""):
    profile = getattr(actor, "procurement_profile", None)
    if profile is None or profile.role != UserProfile.Role.RECEIVER:
        raise ValidationError("Hanya Receiver yang dapat mencatat penerimaan.")
    if po.status == PurchaseOrder.Status.FULFILLED:
        raise ValidationError("PO sudah terpenuhi.")
    receipt = Receipt.objects.create(purchase_order=po, received_by=actor, notes=notes)
    for po_item, quantity in quantities.items():
        quantity = Decimal(quantity)
        if quantity <= 0:
            raise ValidationError("Jumlah penerimaan harus lebih besar dari nol.")
        if quantity > po_item.remaining_quantity:
            raise ValidationError(f"Penerimaan melebihi sisa item {po_item.source_request_item.description}.")
        ReceiptItem.objects.create(
            receipt=receipt, purchase_order_item=po_item, received_quantity=quantity
        )
    refresh_purchase_order_status(po)
    return receipt


def refresh_purchase_order_status(po):
    has_open_discrepancy = po.discrepancies.filter(status=Discrepancy.Status.OPEN).exists()
    all_goods_received = all(
        item.remaining_quantity <= 0
        for item in po.items.filter(source_request_item__item_type="goods")
    )
    all_milestones_done = not po.milestones.exclude(is_completed=True).exists()
    has_goods = po.items.filter(source_request_item__item_type="goods").exists()
    fulfilled = (not has_goods or all_goods_received) and all_milestones_done and not has_open_discrepancy
    po.status = PurchaseOrder.Status.FULFILLED if fulfilled else PurchaseOrder.Status.PARTIALLY_RECEIVED
    po.save(update_fields=["status", "updated_at"])
    request = po.request
    request.status = PurchaseRequest.Status.FULFILLED if fulfilled else PurchaseRequest.Status.PARTIALLY_RECEIVED
    if has_open_discrepancy:
        request.status = PurchaseRequest.Status.DISCREPANCY_OPEN
    request.save(update_fields=["status", "updated_at"])


@transaction.atomic
def complete_milestone(milestone, actor):
    profile = getattr(actor, "procurement_profile", None)
    if profile is None or profile.role not in (
        UserProfile.Role.RECEIVER,
        UserProfile.Role.PROCUREMENT,
    ):
        raise ValidationError("Role tidak berwenang menyelesaikan milestone.")
    if not milestone.is_completed:
        milestone.is_completed = True
        milestone.completed_at = timezone.now()
        milestone.save(update_fields=["is_completed", "completed_at"])
    refresh_purchase_order_status(milestone.purchase_order)


@transaction.atomic
def resolve_discrepancy(discrepancy, actor, notes):
    profile = getattr(actor, "procurement_profile", None)
    if profile is None or profile.role not in (
        UserProfile.Role.RECEIVER,
        UserProfile.Role.PROCUREMENT,
    ):
        raise ValidationError("Role tidak berwenang menyelesaikan discrepancy.")
    if not notes.strip():
        raise ValidationError("Catatan penyelesaian wajib diisi.")
    discrepancy.status = Discrepancy.Status.RESOLVED
    discrepancy.resolution_notes = notes
    discrepancy.resolved_by = actor
    discrepancy.resolved_at = timezone.now()
    discrepancy.save(update_fields=["status", "resolution_notes", "resolved_by", "resolved_at"])
    refresh_purchase_order_status(discrepancy.purchase_order)


@transaction.atomic
def create_discrepancy(po, actor, description):
    profile = getattr(actor, "procurement_profile", None)
    if profile is None or profile.role not in (
        UserProfile.Role.RECEIVER,
        UserProfile.Role.PROCUREMENT,
    ):
        raise ValidationError("Role tidak berwenang membuat discrepancy.")
    if not description.strip():
        raise ValidationError("Deskripsi discrepancy wajib diisi.")
    discrepancy = Discrepancy.objects.create(
        purchase_order=po,
        description=description,
    )
    refresh_purchase_order_status(po)
    return discrepancy


@transaction.atomic
def request_cancellation(request_obj, actor, reason):
    if request_obj.requester_id != actor.id:
        raise ValidationError("Hanya requester pemilik request yang dapat membatalkan.")
    if request_obj.cancellation_requests.filter(
        decision=CancellationRequest.Decision.PENDING
    ).exists():
        raise ValidationError("Sudah ada permintaan pembatalan yang menunggu keputusan.")
    blocked = (
        PurchaseRequest.Status.REJECTED,
        PurchaseRequest.Status.PARTIALLY_RECEIVED,
        PurchaseRequest.Status.DISCREPANCY_OPEN,
        PurchaseRequest.Status.FULFILLED,
        PurchaseRequest.Status.CANCELLED,
        PurchaseRequest.Status.CANCELLATION_PENDING,
    )
    if request_obj.status in blocked:
        raise ValidationError("Pembatalan hanya dapat diajukan sebelum PO dibuat.")
    if hasattr(request_obj, "purchase_order"):
        raise ValidationError("Pembatalan tidak dapat diajukan setelah PO dibuat.")
    cancellation = CancellationRequest.objects.create(
        request=request_obj,
        requested_by=actor,
        reason=reason,
        previous_status=request_obj.status,
    )
    request_obj.previous_status = request_obj.status
    request_obj.status = PurchaseRequest.Status.CANCELLATION_PENDING
    request_obj.save(update_fields=["previous_status", "status", "updated_at"])
    _audit(actor, request_obj, "cancellation_requested", cancellation.previous_status, request_obj.status, reason)
    return cancellation


@transaction.atomic
def decide_cancellation(cancellation, actor, approved, comment=""):
    profile = getattr(actor, "procurement_profile", None)
    if profile is None or profile.role != UserProfile.Role.PROCUREMENT:
        raise ValidationError("Hanya Procurement yang dapat memutuskan pembatalan.")
    if cancellation.decision != CancellationRequest.Decision.PENDING:
        raise ValidationError("Permintaan pembatalan sudah diputuskan.")
    request_obj = cancellation.request
    old_status = request_obj.status
    cancellation.decision = (
        CancellationRequest.Decision.APPROVED
        if approved else CancellationRequest.Decision.REJECTED
    )
    cancellation.reviewed_by = actor
    cancellation.reviewed_at = timezone.now()
    cancellation.save(update_fields=["decision", "reviewed_by", "reviewed_at"])
    request_obj.status = (
        PurchaseRequest.Status.CANCELLED
        if approved else cancellation.previous_status
    )
    request_obj.save(update_fields=["status", "updated_at"])
    _audit(actor, request_obj, "cancellation_decided", old_status, request_obj.status, comment)
