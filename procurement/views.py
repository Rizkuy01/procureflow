import json
from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.utils import timezone

from .forms import (
    CancellationForm,
    DecisionForm,
    DiscrepancyForm,
    PurchaseRequestForm,
    PurchaseRequestItemFormSet,
    ReceiptForm,
    ResolutionForm,
    SupplierEvaluationForm,
    SupplierSelectionForm,
)
from .models import (
    ApprovalAction,
    CancellationRequest,
    Discrepancy,
    PurchaseOrder,
    PurchaseRequest,
    ServiceMilestone,
    SupplierEvaluation,
    UserProfile,
)
from .services import (
    complete_milestone,
    create_purchase_order,
    create_discrepancy,
    decide_cancellation,
    decide_request,
    record_receipt,
    request_cancellation,
    resolve_discrepancy,
    select_final_supplier,
    save_supplier_evaluation,
    reset_approval_after_change,
    submit_request,
)

EDITABLE_BEFORE_PO_STATUSES = (
    PurchaseRequest.Status.DRAFT,
    PurchaseRequest.Status.RETURNED_FOR_CORRECTION,
    PurchaseRequest.Status.PENDING_SECTION_HEAD,
    PurchaseRequest.Status.PENDING_FINANCE,
    PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT,
    PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION,
    PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL,
    PurchaseRequest.Status.APPROVED,
)


@login_required
def dashboard(request):
    profile = getattr(request.user, "procurement_profile", None)
    queue_label = "Request saya"

    # ── Time Range Filtering ──
    period = request.GET.get("period", "all")
    start_date_str = request.GET.get("start_date", "").strip()
    end_date_str = request.GET.get("end_date", "").strip()

    now = timezone.now()
    start_dt = None
    end_dt = None
    period_label = "Semua Waktu"

    if period == "30d":
        start_dt = now - timedelta(days=30)
        period_label = "30 Hari Terakhir"
    elif period == "3m":
        start_dt = now - timedelta(days=90)
        period_label = "3 Bulan Terakhir"
    elif period == "6m":
        start_dt = now - timedelta(days=180)
        period_label = "6 Bulan Terakhir"
    elif period == "this_year":
        start_dt = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_label = f"Tahun {now.year}"
    elif period == "custom" and start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.get_current_timezone())
            period_label = start_date_str
            if end_date_str:
                end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.get_current_timezone()
                )
                period_label += f" s/d {end_date_str}"
        except ValueError:
            start_dt = None
            end_dt = None
            period = "all"
            period_label = "Semua Waktu"
    else:
        period = "all"
        period_label = "Semua Waktu"

    if request.user.is_superuser:
        raw_queue = PurchaseRequest.objects.all()
        queue_label = "Semua request"
    elif not profile or not profile.is_active:
        raw_queue = PurchaseRequest.objects.filter(requester=request.user)
    else:
        queue_filters = {
            UserProfile.Role.SECTION_HEAD: Q(
                status=PurchaseRequest.Status.PENDING_SECTION_HEAD
            ),
            UserProfile.Role.FINANCE: Q(status=PurchaseRequest.Status.PENDING_FINANCE),
            UserProfile.Role.ADMIN_PROCUREMENT: Q(
                status=PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT
            ),
            UserProfile.Role.PROCUREMENT: Q(
                status__in=(
                    PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION,
                    PurchaseRequest.Status.APPROVED,
                    PurchaseRequest.Status.CANCELLATION_PENDING,
                )
            ),
            UserProfile.Role.MANAGERIAL_APPROVER: Q(
                status=PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL
            ),
            UserProfile.Role.RECEIVER: Q(
                purchase_order__status__in=(
                    PurchaseOrder.Status.OPEN,
                    PurchaseOrder.Status.PARTIALLY_RECEIVED,
                )
            ),
        }
        queue_filter = queue_filters.get(profile.role)
        if queue_filter is None:
            raw_queue = PurchaseRequest.objects.filter(requester=request.user)
        else:
            raw_queue = PurchaseRequest.objects.filter(queue_filter)
            queue_label = "Queue tindakan"

    raw_queue = raw_queue.distinct()
    if start_dt:
        raw_queue = raw_queue.filter(created_at__gte=start_dt)
    if end_dt:
        raw_queue = raw_queue.filter(created_at__lte=end_dt)

    action_needed_count = raw_queue.count()
    queue_requests = raw_queue.select_related(
        "requester", "proposed_supplier", "final_supplier"
    ).order_by("-created_at")[:25]

    # Base querysets for PR & PO with date filters
    pr_base = PurchaseRequest.objects.all()
    po_base = PurchaseOrder.objects.all()
    if start_dt:
        pr_base = pr_base.filter(created_at__gte=start_dt)
        po_base = po_base.filter(created_at__gte=start_dt)
    if end_dt:
        pr_base = pr_base.filter(created_at__lte=end_dt)
        po_base = po_base.filter(created_at__lte=end_dt)

    pending_statuses = [
        PurchaseRequest.Status.PENDING_SECTION_HEAD,
        PurchaseRequest.Status.PENDING_FINANCE,
        PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT,
        PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION,
        PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL,
    ]
    if request.user.is_superuser or (
        profile
        and profile.is_active
        and profile.role in (UserProfile.Role.ADMIN_SYSTEM, UserProfile.Role.PROCUREMENT)
    ):
        pending_approval_count = pr_base.filter(
            status__in=pending_statuses
        ).count()
        active_po_count = po_base.filter(
            status__in=(PurchaseOrder.Status.OPEN, PurchaseOrder.Status.PARTIALLY_RECEIVED)
        ).count()
        completed_count = pr_base.filter(
            status=PurchaseRequest.Status.FULFILLED
        ).count()
    elif (
        profile
        and profile.is_active
        and profile.role
        in (
            UserProfile.Role.SECTION_HEAD,
            UserProfile.Role.FINANCE,
            UserProfile.Role.ADMIN_PROCUREMENT,
            UserProfile.Role.MANAGERIAL_APPROVER,
        )
    ):
        pending_approval_count = action_needed_count
        active_po_count = po_base.filter(
            status__in=(PurchaseOrder.Status.OPEN, PurchaseOrder.Status.PARTIALLY_RECEIVED)
        ).count()
        completed_count = pr_base.filter(
            status=PurchaseRequest.Status.FULFILLED
        ).count()
    elif profile and profile.is_active and profile.role == UserProfile.Role.RECEIVER:
        pending_approval_count = 0
        active_po_count = po_base.filter(
            status__in=(PurchaseOrder.Status.OPEN, PurchaseOrder.Status.PARTIALLY_RECEIVED)
        ).count()
        completed_count = po_base.filter(
            status=PurchaseOrder.Status.FULFILLED
        ).count()
    else:
        pending_approval_count = pr_base.filter(
            requester=request.user, status__in=pending_statuses
        ).count()
        active_po_count = po_base.filter(
            request__requester=request.user,
            status__in=(PurchaseOrder.Status.OPEN, PurchaseOrder.Status.PARTIALLY_RECEIVED),
        ).count()
        completed_count = pr_base.filter(
            requester=request.user, status=PurchaseRequest.Status.FULFILLED
        ).count()

    visible_qs = _visible_requests(request.user)
    filtered_visible_qs = visible_qs
    if start_dt:
        filtered_visible_qs = filtered_visible_qs.filter(created_at__gte=start_dt)
    if end_dt:
        filtered_visible_qs = filtered_visible_qs.filter(created_at__lte=end_dt)

    recent_requests = (
        filtered_visible_qs
        .select_related("requester", "proposed_supplier", "final_supplier")
        .order_by("-created_at")[:8]
    )

    can_create_request = (
        request.user.is_superuser
        or not profile
        or not profile.is_active
        or profile.role
        in (
            UserProfile.Role.REQUESTER,
            UserProfile.Role.ADMIN_SYSTEM,
            UserProfile.Role.ADMIN_PROCUREMENT,
        )
    )

    # Total spend calculation (active/approved/fulfilled within filtered date)
    total_spend = filtered_visible_qs.exclude(
        status__in=(
            PurchaseRequest.Status.DRAFT,
            PurchaseRequest.Status.REJECTED,
            PurchaseRequest.Status.CANCELLED,
        )
    ).aggregate(s=Sum("estimated_total"))["s"] or 0

    # Trend Chart Data: Dynamically adapt to period
    month_names_id = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

    if period == "30d":
        chart_months = ["3-4 Mgg Lalu", "2-3 Mgg Lalu", "1-2 Mgg Lalu", "7 Hari Terakhir"]
        chart_spend = []
        chart_counts = []
        intervals = [
            (now - timedelta(days=30), now - timedelta(days=21)),
            (now - timedelta(days=21), now - timedelta(days=14)),
            (now - timedelta(days=14), now - timedelta(days=7)),
            (now - timedelta(days=7), now),
        ]
        for s_i, e_i in intervals:
            w_qs = visible_qs.filter(created_at__gte=s_i, created_at__lte=e_i)
            chart_counts.append(w_qs.count())
            w_spend = w_qs.exclude(
                status__in=(PurchaseRequest.Status.DRAFT, PurchaseRequest.Status.REJECTED, PurchaseRequest.Status.CANCELLED)
            ).aggregate(s=Sum("estimated_total"))["s"] or 0
            chart_spend.append(float(w_spend))
    elif period == "3m":
        chart_months = []
        chart_spend = []
        chart_counts = []
        for i in range(2, -1, -1):
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1
            label = f"{month_names_id[month - 1]} {year}"
            chart_months.append(label)
            m_qs = visible_qs.filter(created_at__year=year, created_at__month=month)
            chart_counts.append(m_qs.count())
            m_spend = m_qs.exclude(
                status__in=(PurchaseRequest.Status.DRAFT, PurchaseRequest.Status.REJECTED, PurchaseRequest.Status.CANCELLED)
            ).aggregate(s=Sum("estimated_total"))["s"] or 0
            chart_spend.append(float(m_spend))
    else:
        # 6m, this_year, all, custom
        num_months = 6 if period == "6m" else (now.month if period == "this_year" else 6)
        chart_months = []
        chart_spend = []
        chart_counts = []
        for i in range(num_months - 1, -1, -1):
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1
            label = f"{month_names_id[month - 1]} {year}"
            chart_months.append(label)
            m_qs = visible_qs.filter(created_at__year=year, created_at__month=month)
            chart_counts.append(m_qs.count())
            m_spend = m_qs.exclude(
                status__in=(PurchaseRequest.Status.DRAFT, PurchaseRequest.Status.REJECTED, PurchaseRequest.Status.CANCELLED)
            ).aggregate(s=Sum("estimated_total"))["s"] or 0
            chart_spend.append(float(m_spend))

    # Status distribution for donut chart (reflects filtered period)
    status_counts = {
        "draft": filtered_visible_qs.filter(status=PurchaseRequest.Status.DRAFT).count(),
        "pending": filtered_visible_qs.filter(status__in=pending_statuses).count(),
        "approved": filtered_visible_qs.filter(
            status__in=(PurchaseRequest.Status.APPROVED, PurchaseRequest.Status.PARTIALLY_RECEIVED)
        ).count(),
        "fulfilled": filtered_visible_qs.filter(status=PurchaseRequest.Status.FULFILLED).count(),
        "rejected": filtered_visible_qs.filter(
            status__in=(
                PurchaseRequest.Status.REJECTED,
                PurchaseRequest.Status.CANCELLED,
                PurchaseRequest.Status.RETURNED_FOR_CORRECTION,
            )
        ).count(),
    }

    chart_data = {
        "months": chart_months,
        "spend": chart_spend,
        "counts": chart_counts,
        "status": status_counts,
    }

    return render(
        request,
        "procurement/dashboard.html",
        {
            "queue_requests": queue_requests,
            "queue_label": queue_label,
            "action_needed_count": action_needed_count,
            "pending_approval_count": pending_approval_count,
            "active_po_count": active_po_count,
            "completed_count": completed_count,
            "recent_requests": recent_requests,
            "can_create_request": can_create_request,
            "total_spend": total_spend,
            "chart_data": chart_data,
            "period": period,
            "period_label": period_label,
            "start_date": start_date_str,
            "end_date": end_date_str,
        },
    )


def _visible_requests(user):
    if user.is_superuser:
        return PurchaseRequest.objects.all()
    profile = getattr(user, "procurement_profile", None)
    if not profile or not profile.is_active:
        return PurchaseRequest.objects.filter(requester=user)

    if profile.role in (UserProfile.Role.ADMIN_SYSTEM, UserProfile.Role.PROCUREMENT):
        return PurchaseRequest.objects.all()

    if profile.role == UserProfile.Role.RECEIVER:
        return PurchaseRequest.objects.filter(
            Q(requester=user)
            | Q(
                purchase_order__status__in=(
                    PurchaseOrder.Status.OPEN,
                    PurchaseOrder.Status.PARTIALLY_RECEIVED,
                    PurchaseOrder.Status.FULFILLED,
                )
            )
        ).distinct()

    role_status = {
        UserProfile.Role.SECTION_HEAD: PurchaseRequest.Status.PENDING_SECTION_HEAD,
        UserProfile.Role.FINANCE: PurchaseRequest.Status.PENDING_FINANCE,
        UserProfile.Role.ADMIN_PROCUREMENT: PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT,
        UserProfile.Role.MANAGERIAL_APPROVER: PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL,
    }
    status = role_status.get(profile.role)
    if status:
        return PurchaseRequest.objects.filter(
            Q(requester=user) | Q(status=status) | Q(approval_actions__approver=user)
        ).distinct()

    return PurchaseRequest.objects.filter(requester=user).distinct()


@login_required
def request_list(request):
    base_queryset = _visible_requests(request.user).select_related(
        "requester", "proposed_supplier", "final_supplier"
    )
    requests = base_queryset.order_by("-created_at")

    # Department filter
    dept_filter = request.GET.get("dept", "").strip()
    if dept_filter:
        requests = requests.filter(department=dept_filter)

    # Search filter
    search_query = request.GET.get("q", "").strip()
    if search_query:
        requests = requests.filter(
            Q(request_no__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(requester__username__icontains=search_query)
            | Q(department__icontains=search_query)
        )

    # Status filter tab
    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        if status_filter == "pending":
            requests = requests.filter(
                status__in=(
                    PurchaseRequest.Status.PENDING_SECTION_HEAD,
                    PurchaseRequest.Status.PENDING_FINANCE,
                    PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT,
                    PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION,
                    PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL,
                )
            )
        elif status_filter == "active_po":
            requests = requests.filter(
                status__in=(
                    PurchaseRequest.Status.APPROVED,
                    PurchaseRequest.Status.PARTIALLY_RECEIVED,
                    PurchaseRequest.Status.DISCREPANCY_OPEN,
                )
            )
        else:
            requests = requests.filter(status=status_filter)

    # Quick metric counts for filter tabs
    all_count = base_queryset.count()
    draft_count = base_queryset.filter(status=PurchaseRequest.Status.DRAFT).count()
    pending_count = base_queryset.filter(
        status__in=(
            PurchaseRequest.Status.PENDING_SECTION_HEAD,
            PurchaseRequest.Status.PENDING_FINANCE,
            PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT,
            PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION,
            PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL,
        )
    ).count()
    active_po_count = base_queryset.filter(
        status__in=(
            PurchaseRequest.Status.APPROVED,
            PurchaseRequest.Status.PARTIALLY_RECEIVED,
            PurchaseRequest.Status.DISCREPANCY_OPEN,
        )
    ).count()
    fulfilled_count = base_queryset.filter(status=PurchaseRequest.Status.FULFILLED).count()

    # Pagination: 10 items per page
    paginator = Paginator(requests, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "procurement/request_list.html",
        {
            "requests": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "search_query": search_query,
            "status_filter": status_filter,
            "dept_filter": dept_filter,
            "departments": PurchaseRequest.Department.choices,
            "all_count": all_count,
            "draft_count": draft_count,
            "pending_count": pending_count,
            "active_po_count": active_po_count,
            "fulfilled_count": fulfilled_count,
        },
    )


@login_required
def request_create(request):
    profile = getattr(request.user, "procurement_profile", None)
    initial_data = {}
    if profile and profile.department:
        initial_data["department"] = profile.department

    if request.method == "POST":
        form = PurchaseRequestForm(request.POST)
        if form.is_valid():
            request_obj = form.save(commit=False)
            request_obj.requester = request.user
            request_obj.save()
            formset = PurchaseRequestItemFormSet(request.POST, instance=request_obj)
            if formset.is_valid():
                formset.save()
                request_obj.refresh_total()
                messages.success(request, "Draft request berhasil disimpan.")
                return redirect("procurement:request-detail", pk=request_obj.pk)
    else:
        form = PurchaseRequestForm(initial=initial_data)
        formset = PurchaseRequestItemFormSet()
    return render(request, "procurement/request_form.html", {"form": form, "formset": formset})


@login_required
def request_edit(request, pk):
    request_obj = get_object_or_404(PurchaseRequest, pk=pk, requester=request.user)
    if request_obj.status not in EDITABLE_BEFORE_PO_STATUSES or hasattr(
        request_obj, "purchase_order"
    ):
        messages.error(request, "Request hanya dapat diedit sebelum PO dibuat.")
        return redirect("procurement:request-detail", pk=pk)
    if request.method == "POST":
        form = PurchaseRequestForm(request.POST, instance=request_obj)
        formset = PurchaseRequestItemFormSet(request.POST, instance=request_obj)
        if form.is_valid() and formset.is_valid():
            previous_total = request_obj.estimated_total
            with transaction.atomic():
                form.save()
                formset.save()
                request_obj.refresh_total()
                approval_reset = reset_approval_after_change(
                    request_obj,
                    request.user,
                    previous_total=previous_total,
                    previous_supplier_id=None,
                )
            if approval_reset:
                messages.success(
                    request,
                    "Request diperbarui. Karena total nominal berubah, approval diulang dari Section Head.",
                )
            else:
                messages.success(request, "Request berhasil diperbarui.")
            return redirect("procurement:request-detail", pk=pk)
    else:
        form = PurchaseRequestForm(instance=request_obj)
        formset = PurchaseRequestItemFormSet(instance=request_obj)
    return render(request, "procurement/request_form.html", {"form": form, "formset": formset, "request_obj": request_obj})


@login_required
def request_detail(request, pk):
    request_obj = get_object_or_404(
        PurchaseRequest.objects.select_related("requester", "proposed_supplier", "final_supplier")
        .prefetch_related("items", "approval_actions__approver"),
        pk=pk,
    )
    if not request.user.is_superuser and request_obj.requester_id != request.user.id:
        profile = getattr(request.user, "procurement_profile", None)
        if profile is None or not profile.is_active:
            messages.error(request, "Anda tidak memiliki akses ke request ini.")
            return redirect("procurement:request-list")
    return render(
        request,
        "procurement/request_detail.html",
        {
            "request_obj": request_obj,
            "has_purchase_order": hasattr(request_obj, "purchase_order"),
            "can_edit_request": (
                request.user.id == request_obj.requester_id
                and request_obj.status in EDITABLE_BEFORE_PO_STATUSES
                and not hasattr(request_obj, "purchase_order")
            ),
        },
    )


@login_required
def request_print(request, pk):
    request_obj = get_object_or_404(
        PurchaseRequest.objects.select_related("requester", "proposed_supplier", "final_supplier")
        .prefetch_related("items", "approval_actions__approver"),
        pk=pk,
    )
    if not request.user.is_superuser and request_obj.requester_id != request.user.id:
        profile = getattr(request.user, "procurement_profile", None)
        if profile is None or not profile.is_active:
            messages.error(request, "Anda tidak memiliki akses ke request ini.")
            return redirect("procurement:request-list")

    # Map approvals by stage for clean signature stamp rendering
    approvals = {}
    for action in request_obj.approval_actions.all():
        approvals[action.stage] = action

    return render(
        request,
        "procurement/request_print.html",
        {
            "request_obj": request_obj,
            "approvals": approvals,
        },
    )


@login_required
def request_submit(request, pk):
    request_obj = get_object_or_404(PurchaseRequest, pk=pk)
    if request.method != "POST":
        return redirect("procurement:request-detail", pk=pk)
    try:
        submit_request(request_obj, request.user)
        messages.success(request, "Request diajukan ke Section Head.")
    except ValidationError as exc:
        messages.error(request, exc.message)
    return redirect("procurement:request-detail", pk=pk)


@login_required
def request_decide(request, pk):
    request_obj = get_object_or_404(PurchaseRequest, pk=pk)
    if request.method != "POST":
        return redirect("procurement:request-detail", pk=pk)
    form = DecisionForm(request.POST)
    if form.is_valid():
        profile = getattr(request.user, "procurement_profile", None)
        stage_by_status = {
            PurchaseRequest.Status.PENDING_SECTION_HEAD: ApprovalAction.Stage.SECTION_HEAD,
            PurchaseRequest.Status.PENDING_FINANCE: ApprovalAction.Stage.FINANCE,
            PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT: ApprovalAction.Stage.ADMIN_PROCUREMENT,
            PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL: ApprovalAction.Stage.MANAGERIAL,
        }
        stage = stage_by_status.get(request_obj.status)
        if profile and profile.role == UserProfile.Role.PROCUREMENT:
            stage = ApprovalAction.Stage.PROCUREMENT
        try:
            if stage is None:
                raise ValidationError("Request belum dapat diputuskan.")
            decide_request(
                request_obj,
                request.user,
                stage,
                form.cleaned_data["decision"],
                form.cleaned_data["comment"],
            )
            messages.success(request, "Keputusan berhasil dicatat.")
        except ValidationError as exc:
            messages.error(request, exc.message)
    return redirect("procurement:request-detail", pk=pk)


@login_required
def supplier_select(request, pk):
    request_obj = get_object_or_404(PurchaseRequest, pk=pk)
    if request.method != "POST":
        form = SupplierSelectionForm(request_obj=request_obj)
    else:
        form = SupplierSelectionForm(request.POST, request_obj=request_obj)
        if form.is_valid():
            try:
                select_final_supplier(request_obj, request.user, form.cleaned_data["final_supplier"])
                messages.success(request, "Supplier final berhasil ditetapkan.")
                return redirect("procurement:request-detail", pk=pk)
            except ValidationError as exc:
                messages.error(request, exc.message)
    return render(request, "procurement/supplier_form.html", {"form": form, "request_obj": request_obj})


@login_required
def supplier_evaluate(request, pk):
    request_obj = get_object_or_404(PurchaseRequest, pk=pk)
    if request.method == "POST":
        form = SupplierEvaluationForm(request.POST, request_obj=request_obj)
        if form.is_valid():
            try:
                save_supplier_evaluation(request_obj, request.user, form.cleaned_data)
                messages.success(request, "Evaluasi supplier berhasil disimpan.")
                return redirect("procurement:supplier-evaluate", pk=pk)
            except ValidationError as exc:
                messages.error(request, exc.message)
    else:
        form = SupplierEvaluationForm(request_obj=request_obj)
    evaluations = request_obj.supplier_evaluations.select_related("supplier", "evaluator")
    return render(
        request,
        "procurement/supplier_evaluation.html",
        {"form": form, "request_obj": request_obj, "evaluations": evaluations},
    )


@login_required
def po_create(request, pk):
    request_obj = get_object_or_404(PurchaseRequest, pk=pk)
    try:
        po = create_purchase_order(request_obj, request.user)
        messages.success(request, f"PO {po.po_no} berhasil dibuat.")
        return redirect("procurement:po-detail", pk=po.pk)
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect("procurement:request-detail", pk=pk)


@login_required
def po_detail(request, pk):
    po = get_object_or_404(
        PurchaseOrder.objects.select_related("request", "supplier").prefetch_related(
            "items__source_request_item", "milestones"
        ),
        pk=pk,
    )
    return render(request, "procurement/po_detail.html", {"po": po})


@login_required
def po_print(request, pk):
    po = get_object_or_404(
        PurchaseOrder.objects.select_related(
            "request__requester", "supplier"
        ).prefetch_related("items__source_request_item"),
        pk=pk,
    )
    if not request.user.is_superuser and po.request.requester_id != request.user.id:
        profile = getattr(request.user, "procurement_profile", None)
        if profile is None or not profile.is_active:
            messages.error(request, "Anda tidak memiliki akses ke PO ini.")
            return redirect("procurement:request-list")
    return render(request, "procurement/po_print.html", {"po": po})


@login_required
def po_receive(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method != "POST":
        form = ReceiptForm(initial={"purchase_order_item": request.GET.get("purchase_order_item")})
    else:
        form = ReceiptForm(request.POST)
        if form.is_valid():
            item = get_object_or_404(po.items, pk=form.cleaned_data["purchase_order_item"])
            try:
                record_receipt(
                    po,
                    request.user,
                    {item: form.cleaned_data["received_quantity"]},
                    form.cleaned_data["notes"],
                )
                messages.success(request, "Penerimaan berhasil dicatat.")
                return redirect("procurement:po-detail", pk=pk)
            except ValidationError as exc:
                messages.error(request, exc.message)
    return render(request, "procurement/receipt_form.html", {"form": form, "po": po})


@login_required
def milestone_complete(request, pk, milestone_pk):
    milestone = get_object_or_404(ServiceMilestone, pk=milestone_pk, purchase_order_id=pk)
    if request.method == "POST":
        try:
            complete_milestone(milestone, request.user)
            messages.success(request, "Milestone ditandai selesai.")
        except ValidationError as exc:
            messages.error(request, exc.message)
    return redirect("procurement:po-detail", pk=pk)


@login_required
def discrepancy_create(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == "POST":
        form = DiscrepancyForm(request.POST)
        if form.is_valid():
            try:
                create_discrepancy(po, request.user, form.cleaned_data["description"])
                messages.success(request, "Discrepancy berhasil dicatat.")
                return redirect("procurement:po-detail", pk=pk)
            except ValidationError as exc:
                messages.error(request, exc.message)
    else:
        form = DiscrepancyForm()
    return render(request, "procurement/discrepancy_form.html", {"form": form, "po": po})


@login_required
def discrepancy_resolve(request, pk, discrepancy_pk):
    discrepancy = get_object_or_404(
        Discrepancy, pk=discrepancy_pk, purchase_order_id=pk
    )
    if request.method == "POST":
        form = ResolutionForm(request.POST)
        if form.is_valid():
            try:
                resolve_discrepancy(
                    discrepancy, request.user, form.cleaned_data["resolution_notes"]
                )
                messages.success(request, "Discrepancy berhasil diselesaikan.")
            except ValidationError as exc:
                messages.error(request, exc.message)
    return redirect("procurement:po-detail", pk=pk)


@login_required
def cancellation_create(request, pk):
    request_obj = get_object_or_404(PurchaseRequest, pk=pk, requester=request.user)
    if request.method == "POST":
        form = CancellationForm(request.POST)
        if form.is_valid():
            try:
                request_cancellation(
                    request_obj, request.user, form.cleaned_data["reason"]
                )
                messages.success(request, "Permintaan pembatalan dikirim ke Procurement.")
                return redirect("procurement:request-detail", pk=pk)
            except ValidationError as exc:
                messages.error(request, exc.message)
    else:
        form = CancellationForm()
    return render(request, "procurement/cancellation_form.html", {"form": form, "request_obj": request_obj})


@login_required
def cancellation_decide(request, pk):
    cancellation = get_object_or_404(
        CancellationRequest.objects.select_related("request"), pk=pk
    )
    if request.method == "POST":
        decision = request.POST.get("decision")
        try:
            decide_cancellation(
                cancellation,
                request.user,
                decision == "approved",
                request.POST.get("comment", ""),
            )
            messages.success(request, "Keputusan pembatalan berhasil dicatat.")
        except ValidationError as exc:
            messages.error(request, exc.message)
    return redirect("procurement:request-detail", pk=cancellation.request_id)
