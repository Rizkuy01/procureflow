import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from procurement.models import (
    ApprovalAction,
    CancellationRequest,
    Discrepancy,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
    Receipt,
    ReceiptItem,
    ServiceMilestone,
    Supplier,
    SupplierEvaluation,
    UserProfile,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed database with realistic procurement dummy data across all roles and workflows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing procurement records before seeding.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Memulai seeding data dummy ProcureFlow..."))

        with transaction.atomic():
            if options["clear"]:
                self.stdout.write("Membersihkan data lama...")
                CancellationRequest.objects.all().delete()
                Discrepancy.objects.all().delete()
                ReceiptItem.objects.all().delete()
                Receipt.objects.all().delete()
                ServiceMilestone.objects.all().delete()
                PurchaseOrderItem.objects.all().delete()
                PurchaseOrder.objects.all().delete()
                SupplierEvaluation.objects.all().delete()
                ApprovalAction.objects.all().delete()
                PurchaseRequestItem.objects.all().delete()
                PurchaseRequest.objects.all().delete()
                Supplier.objects.all().delete()
                self.stdout.write(self.style.SUCCESS("Data lama berhasil dibersihkan."))

            # 1. Setup Users for each role
            users_def = [
                {
                    "username": "requester1",
                    "first_name": "Budi",
                    "last_name": "Santoso",
                    "email": "budi.santoso@procureflow.local",
                    "role": UserProfile.Role.REQUESTER,
                    "department": "it",
                    "band": "",
                },
                {
                    "username": "requester2",
                    "first_name": "Siti",
                    "last_name": "Nurhaliza",
                    "email": "siti.nurhaliza@procureflow.local",
                    "role": UserProfile.Role.REQUESTER,
                    "department": "operations",
                    "band": "",
                },
                {
                    "username": "section_head",
                    "first_name": "Hendra",
                    "last_name": "Wijaya",
                    "email": "hendra.wijaya@procureflow.local",
                    "role": UserProfile.Role.SECTION_HEAD,
                    "department": "it",
                    "band": "",
                },
                {
                    "username": "finance",
                    "first_name": "Ratna",
                    "last_name": "Dewi",
                    "email": "ratna.dewi@procureflow.local",
                    "role": UserProfile.Role.FINANCE,
                    "department": "finance",
                    "band": "",
                },
                {
                    "username": "admin_proc",
                    "first_name": "Dimas",
                    "last_name": "Pratama",
                    "email": "dimas.pratama@procureflow.local",
                    "role": UserProfile.Role.ADMIN_PROCUREMENT,
                    "department": "operations",
                    "band": "",
                },
                {
                    "username": "procurement",
                    "first_name": "Maya",
                    "last_name": "Kusuma",
                    "email": "maya.kusuma@procureflow.local",
                    "role": UserProfile.Role.PROCUREMENT,
                    "department": "operations",
                    "band": "",
                },
                {
                    "username": "manager_x",
                    "first_name": "Bambang",
                    "last_name": "Soediro",
                    "email": "bambang.soediro@procureflow.local",
                    "role": UserProfile.Role.MANAGERIAL_APPROVER,
                    "department": "it",
                    "band": "X",
                },
                {
                    "username": "manager_y",
                    "first_name": "Tirto",
                    "last_name": "Adhi",
                    "email": "tirto.adhi@procureflow.local",
                    "role": UserProfile.Role.MANAGERIAL_APPROVER,
                    "department": "operations",
                    "band": "Y",
                },
                {
                    "username": "manager_z",
                    "first_name": "Zulkifli",
                    "last_name": "Mansyur",
                    "email": "zulkifli.mansyur@procureflow.local",
                    "role": UserProfile.Role.MANAGERIAL_APPROVER,
                    "department": "operations",
                    "band": "Z",
                },
                {
                    "username": "receiver",
                    "first_name": "Joko",
                    "last_name": "Susilo",
                    "email": "joko.susilo@procureflow.local",
                    "role": UserProfile.Role.RECEIVER,
                    "department": "operations",
                    "band": "",
                },
                {
                    "username": "admin_system",
                    "first_name": "Administrator",
                    "last_name": "Sistem",
                    "email": "admin@procureflow.local",
                    "role": UserProfile.Role.ADMIN_SYSTEM,
                    "department": "it",
                    "band": "",
                    "is_staff": True,
                    "is_superuser": True,
                },
            ]

            users = {}
            default_password = "password123"

            for u_data in users_def:
                user, created = User.objects.get_or_create(
                    username=u_data["username"],
                    defaults={
                        "first_name": u_data["first_name"],
                        "last_name": u_data["last_name"],
                        "email": u_data["email"],
                        "is_staff": u_data.get("is_staff", False),
                        "is_superuser": u_data.get("is_superuser", False),
                    },
                )
                user.set_password(default_password)
                user.is_active = True
                user.save()

                profile, _ = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "role": u_data["role"],
                        "department": u_data.get("department", ""),
                        "managerial_band": u_data["band"],
                        "is_active": True,
                    },
                )
                profile.role = u_data["role"]
                profile.department = u_data.get("department", "")
                profile.managerial_band = u_data["band"]
                profile.is_active = True
                profile.save()

                users[u_data["username"]] = user

            # Also ensure current active users (e.g. rizky) has profile if exists
            for existing_user in User.objects.filter(username__in=["rizky", "admin@example.com"]):
                if not hasattr(existing_user, "procurement_profile"):
                    UserProfile.objects.create(
                        user=existing_user,
                        role=UserProfile.Role.ADMIN_SYSTEM,
                        is_active=True,
                    )

            self.stdout.write(self.style.SUCCESS("[OK] 11 Akun User & Role berhasil disiapkan (password: password123)"))

            # 2. Suppliers
            suppliers_def = [
                {
                    "name": "PT Maju Teknologi Solusindo",
                    "contact_name": "Rian Ardiansyah",
                    "contact_email": "sales@majutekno.co.id",
                    "contact_phone": "021-5558123",
                    "notes": "Penyedia hardware IT, workstation, dan perangkat jaringan Cisco & Mikrotik.",
                },
                {
                    "name": "CV Kencana Abadi Furniture",
                    "contact_name": "Agus Gunawan",
                    "contact_email": "info@kencana-furniture.id",
                    "contact_phone": "021-7789456",
                    "notes": "Spesialis perlengkapan kantor, meja ergonomis, dan kursi kerja standar K3.",
                },
                {
                    "name": "PT Sinar Office Perkasa",
                    "contact_name": "Lestari Puji",
                    "contact_email": "lestari@sinaroffice.com",
                    "contact_phone": "021-3344556",
                    "notes": "Distributor resmi ATK, kertas fotokopi, dan cartridge printer.",
                },
                {
                    "name": "PT Mega Cloud Global",
                    "contact_name": "Kevin Wijaya",
                    "contact_email": "enterprise@megacloud.id",
                    "contact_phone": "021-8899001",
                    "notes": "Penyedia server cloud, Managed DevOps, dan SLA Enterprise 99.9%.",
                },
                {
                    "name": "PT Prima Sarana Security",
                    "contact_name": "Budi Hartanto",
                    "contact_email": "security@primasarana.co.id",
                    "contact_phone": "021-6677889",
                    "notes": "Instalasi CCTV Hikvision, sistem RFID door lock biometrik, dan sistem alarm gedung.",
                },
            ]

            suppliers = {}
            for s_data in suppliers_def:
                supplier, _ = Supplier.objects.get_or_create(
                    name=s_data["name"],
                    defaults=s_data,
                )
                suppliers[s_data["name"]] = supplier

            self.stdout.write(self.style.SUCCESS("[OK] 5 Vendor / Supplier mitra resmi berhasil disiapkan"))

            # 3. Create Diverse Purchase Requests across all phases
            today = timezone.now().date()

            # --- Req 1: Draft (Requester 1) ---
            req1 = PurchaseRequest.objects.create(
                requester=users["requester1"],
                title="Pengadaan 5 Unit Laptop High-Performance untuk Tim Engineer",
                purpose="Peremajaan perangkat kerja tim software engineering dan data science untuk percepatan sprint produk Q4.",
                needed_by=today + datetime.timedelta(days=14),
                status=PurchaseRequest.Status.DRAFT,
                proposed_supplier=suppliers["PT Maju Teknologi Solusindo"],
            )
            PurchaseRequestItem.objects.create(
                request=req1,
                description="Laptop Dell Latitude Core i7 32GB RAM 1TB SSD",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("5"),
                unit="unit",
                estimated_unit_price=Decimal("22500000"),
            )
            PurchaseRequestItem.objects.create(
                request=req1,
                description="Monitor Dell UltraSharp 27-inch 4K IPS",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("5"),
                unit="unit",
                estimated_unit_price=Decimal("6200000"),
            )
            req1.refresh_total()

            # --- Req 2: Pending Section Head (Requester 1) ---
            req2 = PurchaseRequest.objects.create(
                requester=users["requester1"],
                title="Pengadaan Server Storage NAS 64TB dan Switch Core 10Gbps",
                purpose="Kebutuhan backup data operasional harian dan peningkatan throughput jaringan lokal data center.",
                needed_by=today + datetime.timedelta(days=10),
                status=PurchaseRequest.Status.PENDING_SECTION_HEAD,
                proposed_supplier=suppliers["PT Maju Teknologi Solusindo"],
            )
            PurchaseRequestItem.objects.create(
                request=req2,
                description="Synology RackStation NAS 64TB Enterprise HDD",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("1"),
                unit="unit",
                estimated_unit_price=Decimal("75000000"),
            )
            PurchaseRequestItem.objects.create(
                request=req2,
                description="Cisco Managed Switch 24-Port 10G SFP+",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("2"),
                unit="unit",
                estimated_unit_price=Decimal("18000000"),
            )
            req2.refresh_total()

            # --- Req 3: Pending Finance (Requester 2) ---
            req3 = PurchaseRequest.objects.create(
                requester=users["requester2"],
                title="Pengadaan Kertas HVS, Tinta Toner, dan Perlengkapan Kantor Q4",
                purpose="Kebutuhan operasional administrasi dokumen legal dan surat-menyurat operasional.",
                needed_by=today + datetime.timedelta(days=7),
                status=PurchaseRequest.Status.PENDING_FINANCE,
                proposed_supplier=suppliers["PT Sinar Office Perkasa"],
            )
            PurchaseRequestItem.objects.create(
                request=req3,
                description="Kertas A4 80gr PaperOne",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("100"),
                unit="rim",
                estimated_unit_price=Decimal("55000"),
            )
            PurchaseRequestItem.objects.create(
                request=req3,
                description="Toner HP LaserJet Original Black",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("10"),
                unit="botol",
                estimated_unit_price=Decimal("850000"),
            )
            req3.refresh_total()
            ApprovalAction.objects.create(
                request=req3,
                stage=ApprovalAction.Stage.SECTION_HEAD,
                approver=users["section_head"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Disetujui. Stok ATK divisi legal sudah di bawah ambang batas minimum.",
            )

            # --- Req 4: Pending Admin Procurement (Requester 2) ---
            req4 = PurchaseRequest.objects.create(
                requester=users["requester2"],
                title="Pemasangan Sistem Access Control Biometrik & 8 Titik CCTV",
                purpose="Meningkatkan keamanan fisik ruang server dan arsip dokumen vital perusahaan.",
                needed_by=today + datetime.timedelta(days=12),
                status=PurchaseRequest.Status.PENDING_ADMIN_PROCUREMENT,
                proposed_supplier=suppliers["PT Prima Sarana Security"],
            )
            PurchaseRequestItem.objects.create(
                request=req4,
                description="Paket Biometric RFID Door Access Standalone",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("2"),
                unit="pintu",
                estimated_unit_price=Decimal("8500000"),
            )
            PurchaseRequestItem.objects.create(
                request=req4,
                description="Kamera CCTV Hikvision IP Camera 4MP Outdoor",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("8"),
                unit="unit",
                estimated_unit_price=Decimal("1250000"),
            )
            req4.refresh_total()
            ApprovalAction.objects.create(
                request=req4,
                stage=ApprovalAction.Stage.SECTION_HEAD,
                approver=users["section_head"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Rekomendasi disetujui untuk audit kepatuhan ISO 27001.",
            )
            ApprovalAction.objects.create(
                request=req4,
                stage=ApprovalAction.Stage.FINANCE,
                approver=users["finance"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Anggaran CAPEX Keamanan Gedung tersedia dan mencukupi.",
            )

            # --- Req 5: Pending Supplier Evaluation (Requester 1) ---
            req5 = PurchaseRequest.objects.create(
                requester=users["requester1"],
                title="Langganan Cloud Infrastructure AWS & Managed Support 12 Bulan",
                purpose="Migrasi core microservices ke cloud dengan jaminan SLA 99.9% uptime dan managed backup.",
                needed_by=today + datetime.timedelta(days=20),
                status=PurchaseRequest.Status.PENDING_SUPPLIER_EVALUATION,
                proposed_supplier=suppliers["PT Mega Cloud Global"],
            )
            PurchaseRequestItem.objects.create(
                request=req5,
                description="Managed Cloud Server AWS High Availability Cluster",
                item_type=PurchaseRequestItem.ItemType.SERVICE,
                quantity=Decimal("12"),
                unit="bulan",
                estimated_unit_price=Decimal("15000000"),
            )
            req5.refresh_total()
            ApprovalAction.objects.create(
                request=req5,
                stage=ApprovalAction.Stage.SECTION_HEAD,
                approver=users["section_head"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Spesifikasi cloud dan SLA telah diverifikasi oleh Lead Architect.",
            )
            ApprovalAction.objects.create(
                request=req5,
                stage=ApprovalAction.Stage.FINANCE,
                approver=users["finance"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Alokasi OPEX IT 2026 telah disesuaikan.",
            )
            ApprovalAction.objects.create(
                request=req5,
                stage=ApprovalAction.Stage.ADMIN_PROCUREMENT,
                approver=users["admin_proc"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Dokumen persyaratan teknis vendor lengkap. Silakan lanjut evaluasi scoring supplier.",
            )
            # Evaluasi supplier
            SupplierEvaluation.objects.create(
                request=req5,
                supplier=suppliers["PT Mega Cloud Global"],
                evaluator=users["procurement"],
                price_score=Decimal("85.00"),
                quality_score=Decimal("92.00"),
                lead_time_score=Decimal("88.00"),
                compliance_score=Decimal("90.00"),
                notes="Vendor merupakan AWS Advanced Tier Partner dengan sertifikasi lengkap.",
            )
            SupplierEvaluation.objects.create(
                request=req5,
                supplier=suppliers["PT Maju Teknologi Solusindo"],
                evaluator=users["procurement"],
                price_score=Decimal("80.00"),
                quality_score=Decimal("78.00"),
                lead_time_score=Decimal("82.00"),
                compliance_score=Decimal("75.00"),
                notes="Pengalaman managed service masih baru dibanding kompetitor.",
            )

            # --- Req 6: Pending Managerial Approval (Requester 2) ---
            req6 = PurchaseRequest.objects.create(
                requester=users["requester2"],
                title="Pengadaan Interior Meja Kerja & Kursi Ergonomis 20 Workstation",
                purpose="Penggantian 20 set meja workstation dan kursi kerja ergonomis untuk ekspansi tim operasional.",
                needed_by=today + datetime.timedelta(days=15),
                status=PurchaseRequest.Status.PENDING_MANAGERIAL_APPROVAL,
                proposed_supplier=suppliers["CV Kencana Abadi Furniture"],
                final_supplier=suppliers["CV Kencana Abadi Furniture"],
            )
            PurchaseRequestItem.objects.create(
                request=req6,
                description="Meja Kerja Modular 4-Seater Partisi Akustik",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("5"),
                unit="set",
                estimated_unit_price=Decimal("11000000"),
            )
            PurchaseRequestItem.objects.create(
                request=req6,
                description="Kursi Ergonomis Mesh Lumbar Support Sihoo M57",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("20"),
                unit="unit",
                estimated_unit_price=Decimal("2000000"),
            )
            req6.refresh_total()
            ApprovalAction.objects.create(
                request=req6,
                stage=ApprovalAction.Stage.SECTION_HEAD,
                approver=users["section_head"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Disetujui untuk peremajaan layout kantor lantai 2.",
            )
            ApprovalAction.objects.create(
                request=req6,
                stage=ApprovalAction.Stage.FINANCE,
                approver=users["finance"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Budget fasilitas kerja tersedia.",
            )
            ApprovalAction.objects.create(
                request=req6,
                stage=ApprovalAction.Stage.ADMIN_PROCUREMENT,
                approver=users["admin_proc"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Vendor terverifikasi dengan portofolio terpercaya.",
            )
            ApprovalAction.objects.create(
                request=req6,
                stage=ApprovalAction.Stage.PROCUREMENT,
                approver=users["procurement"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Final supplier telah ditetapkan dengan skor evaluasi tertinggi.",
            )

            # --- Req 7: Approved & PO Created (PO Open) ---
            req7 = PurchaseRequest.objects.create(
                requester=users["requester1"],
                title="Pengadaan Perangkat UPS Online 20kVA Data Center Gedung A",
                purpose="Proteksi server utama dari pemadaman mendadak dan fluktuasi daya listrik.",
                needed_by=today + datetime.timedelta(days=5),
                status=PurchaseRequest.Status.APPROVED,
                proposed_supplier=suppliers["PT Maju Teknologi Solusindo"],
                final_supplier=suppliers["PT Maju Teknologi Solusindo"],
            )
            item7 = PurchaseRequestItem.objects.create(
                request=req7,
                description="UPS Online 3-Phase 20kVA SNMP Card & External Battery",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("1"),
                unit="unit",
                estimated_unit_price=Decimal("65000000"),
            )
            req7.refresh_total()
            po7 = PurchaseOrder.objects.create(
                request=req7,
                supplier=suppliers["PT Maju Teknologi Solusindo"],
                status=PurchaseOrder.Status.OPEN,
            )
            PurchaseOrderItem.objects.create(
                purchase_order=po7,
                source_request_item=item7,
                ordered_quantity=Decimal("1"),
                unit_price=Decimal("65000000"),
            )

            # --- Req 8: Partially Received (Goods) ---
            req8 = PurchaseRequest.objects.create(
                requester=users["requester1"],
                title="Pengadaan 20 Unit Monitor 24-inch IPS untuk Lab Training Karyawan",
                purpose="Kebutuhan perangkat visual training center dan pelatihan sertifikasi internal.",
                needed_by=today + datetime.timedelta(days=3),
                status=PurchaseRequest.Status.PARTIALLY_RECEIVED,
                proposed_supplier=suppliers["PT Maju Teknologi Solusindo"],
                final_supplier=suppliers["PT Maju Teknologi Solusindo"],
            )
            item8 = PurchaseRequestItem.objects.create(
                request=req8,
                description="Monitor LG 24-inch IPS Full HD 75Hz",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("20"),
                unit="unit",
                estimated_unit_price=Decimal("1750000"),
            )
            req8.refresh_total()
            po8 = PurchaseOrder.objects.create(
                request=req8,
                supplier=suppliers["PT Maju Teknologi Solusindo"],
                status=PurchaseOrder.Status.PARTIALLY_RECEIVED,
            )
            po_item8 = PurchaseOrderItem.objects.create(
                purchase_order=po8,
                source_request_item=item8,
                ordered_quantity=Decimal("20"),
                unit_price=Decimal("1750000"),
            )
            # Catat penerimaan parsial 12 unit
            rcpt8 = Receipt.objects.create(
                purchase_order=po8,
                received_by=users["receiver"],
                notes="Pengiriman batch 1 sebanyak 12 unit telah diterima dalam kondisi segel baik.",
            )
            ReceiptItem.objects.create(
                receipt=rcpt8,
                purchase_order_item=po_item8,
                received_quantity=Decimal("12"),
            )

            # --- Req 9: Fulfilled / Closed ---
            req9 = PurchaseRequest.objects.create(
                requester=users["requester2"],
                title="Pengadaan Lisensi Antivirus Endpoint Security 100 User (1 Tahun)",
                purpose="Proteksi keamanan endpoint workstation dari ancaman malware dan ransomware.",
                needed_by=today - datetime.timedelta(days=2),
                status=PurchaseRequest.Status.FULFILLED,
                proposed_supplier=suppliers["PT Maju Teknologi Solusindo"],
                final_supplier=suppliers["PT Maju Teknologi Solusindo"],
            )
            item9 = PurchaseRequestItem.objects.create(
                request=req9,
                description="Bitdefender GravityZone Business Security 100 Seats",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("100"),
                unit="lisensi",
                estimated_unit_price=Decimal("250000"),
            )
            req9.refresh_total()
            po9 = PurchaseOrder.objects.create(
                request=req9,
                supplier=suppliers["PT Maju Teknologi Solusindo"],
                status=PurchaseOrder.Status.FULFILLED,
            )
            po_item9 = PurchaseOrderItem.objects.create(
                purchase_order=po9,
                source_request_item=item9,
                ordered_quantity=Decimal("100"),
                unit_price=Decimal("250000"),
            )
            rcpt9 = Receipt.objects.create(
                purchase_order=po9,
                received_by=users["receiver"],
                notes="Kunci lisensi digital dan certificate of authenticity telah diterima dan diaktivasi penuh.",
            )
            ReceiptItem.objects.create(
                receipt=rcpt9,
                purchase_order_item=po_item9,
                received_quantity=Decimal("100"),
            )

            # --- Req 10: Discrepancy Open ---
            req10 = PurchaseRequest.objects.create(
                requester=users["requester1"],
                title="Pengadaan 10 Unit Proyektor Laser Ruang Meeting Kantor Pusat",
                purpose="Peremajaan fasilitas ruang rapat dan auditorium presentasi.",
                needed_by=today + datetime.timedelta(days=4),
                status=PurchaseRequest.Status.DISCREPANCY_OPEN,
                proposed_supplier=suppliers["PT Maju Teknologi Solusindo"],
                final_supplier=suppliers["PT Maju Teknologi Solusindo"],
            )
            item10 = PurchaseRequestItem.objects.create(
                request=req10,
                description="Epson Laser Projector 4000 Lumens WXGA",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("10"),
                unit="unit",
                estimated_unit_price=Decimal("9500000"),
            )
            req10.refresh_total()
            po10 = PurchaseOrder.objects.create(
                request=req10,
                supplier=suppliers["PT Maju Teknologi Solusindo"],
                status=PurchaseOrder.Status.PARTIALLY_RECEIVED,
            )
            po_item10 = PurchaseOrderItem.objects.create(
                purchase_order=po10,
                source_request_item=item10,
                ordered_quantity=Decimal("10"),
                unit_price=Decimal("9500000"),
            )
            rcpt10 = Receipt.objects.create(
                purchase_order=po10,
                received_by=users["receiver"],
                notes="Diterima fisik 10 unit pada tanggal pengiriman.",
            )
            ReceiptItem.objects.create(
                receipt=rcpt10,
                purchase_order_item=po_item10,
                received_quantity=Decimal("10"),
            )
            Discrepancy.objects.create(
                purchase_order=po10,
                receipt=rcpt10,
                description="Ditemukan 2 unit proyektor mengalami cacat lensa (bergaris) saat unboxing dan uji coba. Menunggu konfirmasi penggantian unit baru (RMA) dari pihak vendor.",
                status=Discrepancy.Status.OPEN,
            )

            # --- Req 11: Returned for Correction ---
            req11 = PurchaseRequest.objects.create(
                requester=users["requester2"],
                title="Pengadaan 8 Unit Smartphone Operasional Tim Kurir & Logistik",
                purpose="Perangkat input aplikasi manifest kurir dan tracking armada delivery.",
                needed_by=today + datetime.timedelta(days=10),
                status=PurchaseRequest.Status.RETURNED_FOR_CORRECTION,
                proposed_supplier=suppliers["PT Maju Teknologi Solusindo"],
            )
            PurchaseRequestItem.objects.create(
                request=req11,
                description="Smartphone Android RAM 4GB Baterai 5000mAh",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("8"),
                unit="unit",
                estimated_unit_price=Decimal("1800000"),
            )
            req11.refresh_total()
            ApprovalAction.objects.create(
                request=req11,
                stage=ApprovalAction.Stage.SECTION_HEAD,
                approver=users["section_head"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Kebutuhan armada kurir disetujui.",
            )
            ApprovalAction.objects.create(
                request=req11,
                stage=ApprovalAction.Stage.FINANCE,
                approver=users["finance"],
                decision=ApprovalAction.Decision.APPROVED,
                comment="Budget operasional disetujui.",
            )
            ApprovalAction.objects.create(
                request=req11,
                stage=ApprovalAction.Stage.ADMIN_PROCUREMENT,
                approver=users["admin_proc"],
                decision=ApprovalAction.Decision.RETURNED,
                comment="Mohon cantumkan merk spesifik, sertifikat garansi resmi, dan kelengkapan casing tahan banting sesuai SOP logistik.",
            )

            # --- Req 12: Cancellation Pending ---
            req12 = PurchaseRequest.objects.create(
                requester=users["requester1"],
                title="Pengadaan Tablet Android 10-inch untuk Digital Signage Resepsionis",
                purpose="Display selamat datang dan registrasi tamu digital di lobby utama.",
                needed_by=today + datetime.timedelta(days=12),
                status=PurchaseRequest.Status.CANCELLATION_PENDING,
                previous_status=PurchaseRequest.Status.PENDING_SECTION_HEAD,
                proposed_supplier=suppliers["PT Maju Teknologi Solusindo"],
            )
            PurchaseRequestItem.objects.create(
                request=req12,
                description="Tablet Android 10-inch dengan Wall Mount",
                item_type=PurchaseRequestItem.ItemType.GOODS,
                quantity=Decimal("2"),
                unit="unit",
                estimated_unit_price=Decimal("3500000"),
            )
            req12.refresh_total()
            CancellationRequest.objects.create(
                request=req12,
                requested_by=users["requester1"],
                reason="Lobby utama diputuskan menggunakan smart TV yang sudah tersedia di gudang perlengkapan, sehingga tablet display tidak lagi diperlukan.",
                decision=CancellationRequest.Decision.PENDING,
                previous_status=PurchaseRequest.Status.PENDING_SECTION_HEAD,
            )

            # Service Milestone demo on Req 5 (Cloud service) if PO created in future
            # Let's also add 2 Service Milestones on PO 7 or standalone
            ServiceMilestone.objects.create(
                purchase_order=po7,
                name="Instalasi Fisik UPS & Wiring Panel Listrik Gedung",
                due_date=today + datetime.timedelta(days=7),
                is_completed=True,
                completed_at=timezone.now(),
                notes="Kabel grounding dan MCB 63A sudah terpasang rapi.",
            )
            ServiceMilestone.objects.create(
                purchase_order=po7,
                name="Uji Coba Load Test & Cutover Daya Listrik Utama",
                due_date=today + datetime.timedelta(days=14),
                is_completed=False,
                notes="Menunggu jadwal maintenance window akhir pekan.",
            )

        self.stdout.write(self.style.SUCCESS("[OK] 12 Purchase Requests dengan beragam status & workflow berhasil dibuat"))
        self.stdout.write(self.style.SUCCESS("[OK] Purchase Orders, Penerimaan (Receipts), Evaluasi Supplier, & Discrepancies terhubung rapi."))

        self.stdout.write("\n" + "=" * 65)
        self.stdout.write(self.style.SUCCESS(" DAFTAR AKUN PENGUJIAN (PASSWORD: password123)"))
        self.stdout.write("=" * 65)
        accounts_summary = [
            ("requester1", "Requester (IT)", "Draft, Pending, Discrepancy"),
            ("requester2", "Requester (Office)", "Pending, Returned, Fulfilled"),
            ("section_head", "Section Head", "Approval Queue Tahap 1"),
            ("finance", "Finance Approver", "Approval Queue Tahap 2"),
            ("admin_proc", "Admin Procurement", "Approval Queue Tahap 3 / Return"),
            ("procurement", "Procurement Specialist", "Evaluasi Vendor & Buat PO"),
            ("manager_x", "Managerial Approver (Band X)", "Approval Nominal Tinggi"),
            ("receiver", "Receiver (Gudang/Logistik)", "Catat Penerimaan & Cek Selisih"),
            ("admin_system", "Admin System / Superuser", "Full Access & Django Admin"),
        ]
        for username, role, desc in accounts_summary:
            self.stdout.write(f" * {username:<15} | {role:<28} | {desc}")
        self.stdout.write("=" * 65)
        self.stdout.write(self.style.SUCCESS("Seeder selesai dengan sukses!\n"))
