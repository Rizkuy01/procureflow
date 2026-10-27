from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal

from .decorators import has_role
from .models import (
    AuditEvent,
    CancellationRequest,
    Discrepancy,
    PurchaseOrder,
    PurchaseRequest,
    PurchaseRequestItem,
    Supplier,
    SupplierEvaluation,
    UserProfile,
)
from .services import (
    create_purchase_order,
    record_receipt,
    refresh_purchase_order_status,
    request_cancellation,
    decide_cancellation,
    save_supplier_evaluation,
    select_final_supplier,
    reset_approval_after_change,
)


class AccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="requester",
            password="test-password",
        )
        UserProfile.objects.create(
            user=self.user,
            role=UserProfile.Role.REQUESTER,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("procurement:dashboard"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('procurement:dashboard')}",
        )

    def test_authenticated_user_can_open_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("procurement:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Requester")

    def test_inactive_profile_has_no_role_access(self):
        self.user.procurement_profile.is_active = False
        self.user.procurement_profile.save()
        self.assertFalse(has_role(self.user, UserProfile.Role.REQUESTER))

    def test_dashboard_shows_requester_queue(self):
        supplier = Supplier.objects.create(name="Dashboard Supplier")
        PurchaseRequest.objects.create(
            requester=self.user,
            title="My dashboard request",
            purpose="Queue test",
            needed_by="2026-12-01",
            proposed_supplier=supplier,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("procurement:dashboard"))
        self.assertContains(response, "My dashboard request")

    def test_dashboard_shows_only_role_action_queue(self):
        approver = get_user_model().objects.create_user(username="dashboard-finance")
        UserProfile.objects.create(user=approver, role=UserProfile.Role.FINANCE)
        supplier = Supplier.objects.create(name="Queue Supplier")
        PurchaseRequest.objects.create(
            requester=self.user,
            title="Finance queue request",
            purpose="Queue test",
            needed_by="2026-12-01",
            proposed_supplier=supplier,
            status=PurchaseRequest.Status.PENDING_FINANCE,
        )
        PurchaseRequest.objects.create(
            requester=self.user,
            title="Not finance queue",
            purpose="Queue test",
            needed_by="2026-12-01",
            proposed_supplier=supplier,
            status=PurchaseRequest.Status.PENDING_SECTION_HEAD,
        )
        self.client.force_login(approver)
        response = self.client.get(reverse("procurement:dashboard"))
        self.assertContains(response, "Finance queue request")
        self.assertNotContains(response, "Not finance queue")

    def test_request_list_pagination_per_10(self):
        supplier = Supplier.objects.create(name="Pagination Supplier")
        for i in range(15):
            PurchaseRequest.objects.create(
                requester=self.user,
                title=f"Request Batch {i+1}",
                purpose="Testing pagination",
                needed_by="2026-12-01",
                proposed_supplier=supplier,
            )
        self.client.force_login(self.user)
        # Page 1: should have 10 items
        response = self.client.get(reverse("procurement:request-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["requests"]), 10)
        self.assertTrue(response.context["page_obj"].has_next())
        self.assertFalse(response.context["page_obj"].has_previous())

        # Page 2: should have remaining 5 items
        response2 = self.client.get(reverse("procurement:request-list") + "?page=2")
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(len(response2.context["requests"]), 5)
        self.assertFalse(response2.context["page_obj"].has_next())
        self.assertTrue(response2.context["page_obj"].has_previous())

    def test_request_list_filter_by_department(self):
        supplier = Supplier.objects.create(name="Dept Supplier")
        PurchaseRequest.objects.create(
            requester=self.user,
            title="IT Request",
            department="it",
            purpose="IT assets",
            needed_by="2026-12-01",
            proposed_supplier=supplier,
        )
        PurchaseRequest.objects.create(
            requester=self.user,
            title="Finance Request",
            department="finance",
            purpose="Finance assets",
            needed_by="2026-12-01",
            proposed_supplier=supplier,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("procurement:request-list") + "?dept=it")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "IT Request")
        self.assertNotContains(response, "Finance Request")

    def test_request_create_prepopulates_user_department(self):
        self.user.procurement_profile.department = "it"
        self.user.procurement_profile.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse("procurement:request-create"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial.get("department"), "it")



class ProcurementModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="model-requester",
            password="test-password",
        )
        self.supplier = Supplier.objects.create(name="Supplier One")
        self.request = PurchaseRequest.objects.create(
            requester=self.user,
            title="Laptop",
            purpose="Equipment",
            needed_by="2026-12-01",
            proposed_supplier=self.supplier,
        )

    def test_request_total_is_calculated_from_items(self):
        PurchaseRequestItem.objects.create(
            request=self.request,
            description="Laptop",
            item_type=PurchaseRequestItem.ItemType.GOODS,
            quantity=2,
            unit="unit",
            estimated_unit_price="1250000.00",
        )
        PurchaseRequestItem.objects.create(
            request=self.request,
            description="Installation",
            item_type=PurchaseRequestItem.ItemType.SERVICE,
            quantity=1,
            unit="milestone",
            estimated_unit_price="250000.00",
        )
        self.assertEqual(self.request.calculate_total(), 2750000)

    def test_item_rejects_non_positive_quantity(self):
        item = PurchaseRequestItem(
            request=self.request,
            description="Invalid",
            item_type=PurchaseRequestItem.ItemType.GOODS,
            quantity=0,
            unit="unit",
            estimated_unit_price="10.00",
        )
        with self.assertRaisesMessage(Exception, "greater than zero"):
            item.full_clean()


class WorkflowTests(TestCase):
    def setUp(self):
        self.requester = get_user_model().objects.create_user(username="flow-requester")
        UserProfile.objects.create(
            user=self.requester, role=UserProfile.Role.REQUESTER
        )
        self.section_head = get_user_model().objects.create_user(username="section-head")
        UserProfile.objects.create(
            user=self.section_head, role=UserProfile.Role.SECTION_HEAD
        )
        self.supplier = Supplier.objects.create(name="Flow Supplier")
        self.request = PurchaseRequest.objects.create(
            requester=self.requester,
            title="Flow request",
            purpose="Testing",
            needed_by="2026-12-01",
            proposed_supplier=self.supplier,
        )
        PurchaseRequestItem.objects.create(
            request=self.request,
            description="Item",
            item_type=PurchaseRequestItem.ItemType.GOODS,
            quantity=1,
            unit="unit",
            estimated_unit_price="1000000.00",
        )

    def test_requester_can_submit_request(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse("procurement:request-submit", args=[self.request.pk])
        )
        self.assertRedirects(
            response, reverse("procurement:request-detail", args=[self.request.pk])
        )
        self.request.refresh_from_db()
        self.assertEqual(
            self.request.status, PurchaseRequest.Status.PENDING_SECTION_HEAD
        )

    def test_section_head_can_approve_but_requester_cannot(self):
        self.request.status = PurchaseRequest.Status.PENDING_SECTION_HEAD
        self.request.save(update_fields=["status"])
        self.client.force_login(self.requester)
        self.client.post(
            reverse("procurement:request-decide", args=[self.request.pk]),
            {"decision": "approved", "comment": ""},
        )
        self.request.refresh_from_db()
        self.assertEqual(
            self.request.status, PurchaseRequest.Status.PENDING_SECTION_HEAD
        )
        self.client.force_login(self.section_head)
        self.client.post(
            reverse("procurement:request-decide", args=[self.request.pk]),
            {"decision": "approved", "comment": "OK"},
        )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, PurchaseRequest.Status.PENDING_FINANCE)


class FulfillmentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.requester = User.objects.create_user(username="fulfill-requester")
        self.procurement = User.objects.create_user(username="fulfill-procurement")
        self.receiver = User.objects.create_user(username="fulfill-receiver")
        UserProfile.objects.create(user=self.procurement, role=UserProfile.Role.PROCUREMENT)
        UserProfile.objects.create(user=self.receiver, role=UserProfile.Role.RECEIVER)
        supplier = Supplier.objects.create(name="Fulfillment Supplier")
        self.request = PurchaseRequest.objects.create(
            requester=self.requester,
            title="Fulfillment",
            purpose="Testing",
            needed_by="2026-12-01",
            proposed_supplier=supplier,
            final_supplier=supplier,
            status=PurchaseRequest.Status.APPROVED,
        )
        self.item = PurchaseRequestItem.objects.create(
            request=self.request,
            description="Monitor",
            item_type=PurchaseRequestItem.ItemType.GOODS,
            quantity=10,
            unit="unit",
            estimated_unit_price="100.00",
        )
        self.request.refresh_total()
        self.po = create_purchase_order(self.request, self.procurement)
        self.po_item = self.po.items.get()

    def test_po_requires_final_supplier_and_partial_receipt_updates_status(self):
        record_receipt(self.po, self.receiver, {self.po_item: "4"})
        self.po.refresh_from_db()
        self.request.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.PARTIALLY_RECEIVED)
        self.assertEqual(self.request.status, PurchaseRequest.Status.PARTIALLY_RECEIVED)
        self.assertEqual(self.po_item.remaining_quantity, 6)

    def test_po_print_page_is_available_to_active_profile(self):
        self.client.force_login(self.receiver)
        response = self.client.get(reverse("procurement:po-print", args=[self.po.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.po.po_no)
        self.assertContains(response, "Simpan PDF")

    def test_po_print_page_requires_access(self):
        outsider = get_user_model().objects.create_user(username="po-outsider")
        self.client.force_login(outsider)
        response = self.client.get(reverse("procurement:po-print", args=[self.po.pk]))
        self.assertRedirects(response, reverse("procurement:request-list"))

    def test_request_print_page_is_available_to_requester(self):
        self.client.force_login(self.requester)
        response = self.client.get(reverse("procurement:request-print", args=[self.request.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.request.request_no)
        self.assertContains(response, "Purchase Requisition")
        self.assertContains(response, "Cetak / Simpan ke PDF")

    def test_request_print_page_requires_access(self):
        outsider = get_user_model().objects.create_user(username="req-outsider")
        self.client.force_login(outsider)
        response = self.client.get(reverse("procurement:request-print", args=[self.request.pk]))
        self.assertRedirects(response, reverse("procurement:request-list"))

    def test_over_receipt_is_rejected(self):
        with self.assertRaisesMessage(Exception, "melebihi sisa"):
            record_receipt(self.po, self.receiver, {self.po_item: "11"})

    def test_open_discrepancy_blocks_fulfillment(self):
        record_receipt(self.po, self.receiver, {self.po_item: "10"})
        Discrepancy.objects.create(
            purchase_order=self.po,
            description="Damaged packaging",
        )
        refresh_purchase_order_status(self.po)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, PurchaseRequest.Status.DISCREPANCY_OPEN)


class CancellationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.requester = User.objects.create_user(username="cancel-requester")
        self.procurement = User.objects.create_user(username="cancel-procurement")
        UserProfile.objects.create(
            user=self.requester, role=UserProfile.Role.REQUESTER
        )
        UserProfile.objects.create(
            user=self.procurement, role=UserProfile.Role.PROCUREMENT
        )
        supplier = Supplier.objects.create(name="Cancellation Supplier")
        self.request = PurchaseRequest.objects.create(
            requester=self.requester,
            title="Cancel me",
            purpose="Testing cancellation",
            needed_by="2026-12-01",
            proposed_supplier=supplier,
            status=PurchaseRequest.Status.PENDING_FINANCE,
        )

    def test_requester_can_request_cancellation_before_po(self):
        cancellation = request_cancellation(
            self.request, self.requester, "Budget is no longer available."
        )
        self.request.refresh_from_db()
        self.assertEqual(
            self.request.status, PurchaseRequest.Status.CANCELLATION_PENDING
        )
        self.assertEqual(cancellation.previous_status, PurchaseRequest.Status.PENDING_FINANCE)
        self.assertTrue(
            self.request.cancellation_requests.filter(
                decision=CancellationRequest.Decision.PENDING
            ).exists()
        )

    def test_rejected_cancellation_restores_previous_status(self):
        cancellation = request_cancellation(
            self.request, self.requester, "Need to review the requirement."
        )
        decide_cancellation(cancellation, self.procurement, approved=False)
        self.request.refresh_from_db()
        cancellation.refresh_from_db()
        self.assertEqual(
            self.request.status, PurchaseRequest.Status.PENDING_FINANCE
        )
        self.assertEqual(cancellation.decision, CancellationRequest.Decision.REJECTED)
        self.assertEqual(cancellation.reviewed_by, self.procurement)

    def test_approved_cancellation_sets_cancelled_status(self):
        cancellation = request_cancellation(
            self.request, self.requester, "Project has been stopped."
        )
        decide_cancellation(cancellation, self.procurement, approved=True)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, PurchaseRequest.Status.CANCELLED)

    def test_second_pending_cancellation_is_rejected(self):
        request_cancellation(self.request, self.requester, "First reason.")
        with self.assertRaisesMessage(Exception, "Sudah ada permintaan pembatalan"):
            request_cancellation(self.request, self.requester, "Second reason.")

    def test_cancellation_is_rejected_after_po_exists(self):
        supplier = Supplier.objects.create(name="Existing PO Supplier")
        self.request.status = PurchaseRequest.Status.APPROVED
        self.request.final_supplier = supplier
        self.request.save(update_fields=["status", "final_supplier"])
        item = PurchaseRequestItem.objects.create(
            request=self.request,
            description="Ordered item",
            item_type=PurchaseRequestItem.ItemType.GOODS,
            quantity=1,
            unit="unit",
            estimated_unit_price="100.00",
        )
        create_purchase_order(self.request, self.procurement)
        with self.assertRaisesMessage(Exception, "setelah PO dibuat"):
            request_cancellation(self.request, self.requester, "Too late.")


class SupplierEvaluationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.requester = User.objects.create_user(username="evaluation-requester")
        self.procurement = User.objects.create_user(username="evaluation-procurement")
        UserProfile.objects.create(
            user=self.procurement, role=UserProfile.Role.PROCUREMENT
        )
        self.supplier = Supplier.objects.create(name="Evaluation Supplier")
        self.request = PurchaseRequest.objects.create(
            requester=self.requester,
            title="Supplier evaluation",
            purpose="Compare suppliers",
            needed_by="2026-12-01",
            proposed_supplier=self.supplier,
            status=PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION,
        )

    def evaluation_data(self, supplier=None):
        return {
            "supplier": supplier or self.supplier,
            "price_score": "80",
            "quality_score": "90",
            "lead_time_score": "70",
            "compliance_score": "100",
            "notes": "Evaluasi awal",
        }

    def test_combined_score_is_average_of_all_criteria(self):
        evaluation = save_supplier_evaluation(
            self.request, self.procurement, self.evaluation_data()
        )
        self.assertEqual(evaluation.total_score, 85)

    def test_supplier_must_be_evaluated_before_final_selection(self):
        with self.assertRaisesMessage(Exception, "harus dievaluasi"):
            select_final_supplier(self.request, self.procurement, self.supplier)
        save_supplier_evaluation(
            self.request, self.procurement, self.evaluation_data()
        )
        select_final_supplier(self.request, self.procurement, self.supplier)
        self.request.refresh_from_db()
        self.assertEqual(
            self.request.status, PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL
        )

    def test_scores_must_be_between_zero_and_one_hundred(self):
        data = self.evaluation_data()
        data["quality_score"] = "101"
        evaluation = SupplierEvaluation(
            request=self.request,
            evaluator=self.procurement,
            **data,
        )
        with self.assertRaisesMessage(Exception, "antara 0 dan 100"):
            evaluation.full_clean()


class ReapprovalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.requester = User.objects.create_user(username="reapproval-requester")
        UserProfile.objects.create(
            user=self.requester, role=UserProfile.Role.REQUESTER
        )
        self.supplier = Supplier.objects.create(name="Original Supplier")
        self.new_supplier = Supplier.objects.create(name="New Supplier")
        self.request = PurchaseRequest.objects.create(
            requester=self.requester,
            title="Reapproval request",
            purpose="Test approval reset",
            needed_by="2026-12-01",
            proposed_supplier=self.supplier,
            final_supplier=self.supplier,
            estimated_total="1500000.00",
            status=PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL,
        )
        PurchaseRequestItem.objects.create(
            request=self.request,
            description="Item",
            item_type=PurchaseRequestItem.ItemType.GOODS,
            quantity=1,
            unit="unit",
            estimated_unit_price="1500000.00",
        )
        SupplierEvaluation.objects.create(
            request=self.request,
            supplier=self.supplier,
            evaluator=self.requester,
            price_score=80,
            quality_score=80,
            lead_time_score=80,
            compliance_score=80,
        )

    def test_nominal_change_resets_approval_and_clears_supplier_selection(self):
        changed_total = Decimal(str(self.request.estimated_total)) + 100
        self.request.estimated_total = changed_total
        self.request.save(update_fields=["estimated_total"])
        reset = reset_approval_after_change(
            self.request,
            self.requester,
            previous_total="1500000.00",
            previous_supplier_id=self.supplier.pk,
        )
        self.assertTrue(reset)
        self.request.refresh_from_db()
        self.assertEqual(
            self.request.status, PurchaseRequest.Status.PENDING_SECTION_HEAD
        )
        self.assertIsNone(self.request.final_supplier)
        self.assertFalse(self.request.supplier_evaluations.exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                entity_type="PurchaseRequest",
                entity_id=str(self.request.pk),
                action="approval_reset",
            ).exists()
        )

    def test_unchanged_request_does_not_reset_approval(self):
        reset = reset_approval_after_change(
            self.request,
            self.requester,
            previous_total=Decimal(str(self.request.estimated_total)),
            previous_supplier_id=self.supplier.pk,
        )
        self.assertFalse(reset)
        self.request.refresh_from_db()
        self.assertEqual(
            self.request.status, PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL
        )

    def test_supplier_change_resets_approval(self):
        self.request.proposed_supplier = self.new_supplier
        self.request.save(update_fields=["proposed_supplier"])
        reset_approval_after_change(
            self.request,
            self.requester,
            previous_total=Decimal(str(self.request.estimated_total)),
            previous_supplier_id=self.supplier.pk,
        )
        self.request.refresh_from_db()
        self.assertEqual(
            self.request.status, PurchaseRequest.Status.PENDING_SECTION_HEAD
        )
        self.assertIsNone(self.request.final_supplier)


class WBSChecklistTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.requester = User.objects.create_user(username="wbs-requester")
        self.section_head = User.objects.create_user(username="wbs-section-head")
        self.finance = User.objects.create_user(username="wbs-finance")
        self.admin_proc = User.objects.create_user(username="wbs-admin-proc")

        UserProfile.objects.create(user=self.requester, role=UserProfile.Role.REQUESTER)
        UserProfile.objects.create(user=self.section_head, role=UserProfile.Role.SECTION_HEAD)
        UserProfile.objects.create(user=self.finance, role=UserProfile.Role.FINANCE)
        UserProfile.objects.create(user=self.admin_proc, role=UserProfile.Role.ADMIN_PROCUREMENT)

        self.supplier = Supplier.objects.create(name="WBS Supplier")

    def test_t01_managerial_matrix_at_one_million_is_pak_x(self):
        from .services import managerial_approver_for
        self.assertEqual(managerial_approver_for(Decimal("1000000.00")), "Pak X")

    def test_t02_managerial_matrix_above_one_million_is_pak_y(self):
        from .services import managerial_approver_for
        self.assertEqual(managerial_approver_for(Decimal("1000001.00")), "Pak Y")

    def test_t03_managerial_matrix_at_ten_million_is_pak_y(self):
        from .services import managerial_approver_for
        self.assertEqual(managerial_approver_for(Decimal("10000000.00")), "Pak Y")

    def test_t04_managerial_matrix_above_ten_million_is_pak_z(self):
        from .services import managerial_approver_for
        self.assertEqual(managerial_approver_for(Decimal("10000001.00")), "Pak Z")

    def test_t05_finance_cannot_approve_before_section_head(self):
        from .services import decide_request
        from .models import ApprovalAction
        req = PurchaseRequest.objects.create(
            requester=self.requester,
            title="T-05 Test",
            purpose="Testing order",
            needed_by="2026-12-01",
            proposed_supplier=self.supplier,
            status=PurchaseRequest.Status.PENDING_SECTION_HEAD,
        )
        with self.assertRaisesMessage(Exception, "belum berada pada tahap approval ini"):
            decide_request(
                req,
                self.finance,
                ApprovalAction.Stage.FINANCE,
                ApprovalAction.Decision.APPROVED,
            )

    def test_t06_admin_procurement_cannot_final_reject(self):
        from .services import decide_request
        from .models import ApprovalAction
        req = PurchaseRequest.objects.create(
            requester=self.requester,
            title="T-06 Test",
            purpose="Testing return only",
            needed_by="2026-12-01",
            proposed_supplier=self.supplier,
            status=PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT,
        )
        with self.assertRaisesMessage(Exception, "hanya dapat mengembalikan untuk koreksi"):
            decide_request(
                req,
                self.admin_proc,
                ApprovalAction.Stage.ADMIN_PROCUREMENT,
                ApprovalAction.Decision.REJECTED,
            )
