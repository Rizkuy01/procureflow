# ProcureFlow — Procurement Management System

Sistem Manajemen Pengadaan Barang dan Jasa (*Procurement Management System*) berbasis web yang dibangun menggunakan **Django (Python)**. Sistem ini mendigitalkan seluruh tahapan proses pengadaan dari pengajuan permintaan (*purchase request*), pemeriksaan administrasi, persetujuan bertingkat (*multi-stage approval*), evaluasi dan penetapan vendor, penerbitan *Purchase Order* (PO), hingga penerimaan barang parsial (*goods/service receipt*) dan penanganan ketidaksesuaian (*discrepancy*).

Sistem ini dirancang dan diimplementasikan secara ketat mengacu pada:
* **Business Requirement Document (BRD)**: [guide/BRD_Procurement_Management_System_Django.docx](guide/BRD_Procurement_Management_System_Django.docx)
* **Product Requirement Document (PRD)**: [guide/PRD_Procurement_Management_System_Django.docx](guide/PRD_Procurement_Management_System_Django.docx)
* **Work Breakdown Structure (WBS)**: [guide/WBS_Procurement_Management_System.xlsx](guide/WBS_Procurement_Management_System.xlsx)
* **Diagram Alur Proses BPMN**:
  - Alur Utama: [guide/flow utama.png](guide/flow%20utama.png)
  - Alur Pembatalan: [guide/flow pembatalan.png](guide/flow%20pembatalan.png)

---

## Daftar Isi
1. [Fitur Utama & Alur Bisnis](#fitur-utama--alur-bisnis)
2. [Matriks Peran Pengguna (RBAC)](#matriks-peran-pengguna-rbac)
3. [Prasyarat Sistem](#prasyarat-sistem)
4. [Langkah Instalasi](#langkah-instalasi)
5. [Data Pengguna (User Management)](#data-pengguna-user-management)
   - [Opsi A: Template Akun Siap Pakai (Seeder Data)](#opsi-a-template-akun-siap-pakai-seeder-data-rekomendasi)
   - [Opsi B: Membuat User & Role Baru Secara Manual](#opsi-b-membuat-user--role-baru-secara-manual)
6. [Menjalankan Aplikasi](#menjalankan-aplikasi)
7. [Panduan Skenario Demo & Pengujian](#panduan-skenario-demo--pengujian)
8. [Menjalankan Automated Tests](#menjalankan-automated-tests)
9. [Struktur Direktori Proyek](#struktur-direktori-proyek)

---

## Fitur Utama & Alur Bisnis

### 1. Alur Pengadaan Utama (BPMN Flow Utama)
1. **Pembuatan Permintaan (*Purchase Request*)**:
   - Requester mengisi judul, tujuan, tanggal kebutuhan, dan supplier yang diusulkan.
   - Form dinamis dengan tata letak dua kolom: informasi umum di sisi kiri dan accordion interaktif untuk rincian item barang/jasa di sisi kanan.
   - Validasi otomatis: minimal 1 baris item, kuantitas positif ($>0$), dan estimasi harga non-negatif.
2. **Review Section Head**:
   - Meninjau pengajuan awal; dapat menyetujui (*Approve*) atau menolak final (*Final Reject*).
3. **Review Finance**:
   - Memeriksa ketersediaan anggaran belanja (CAPEX/OPEX); dapat *Approve* atau *Final Reject*.
4. **Pemeriksaan Admin Procurement**:
   - Memeriksa kelengkapan berkas dan dokumen pendukung.
   - **Aturan Bisnis (BR-04 / WBS 5.3)**: Admin Procurement **tidak memiliki hak penolakan final (*No Final Reject*)**, melainkan dapat mengembalikan permintaan ke Requester untuk dikoreksi (*Return for Correction*).
5. **Evaluasi & Penetapan Supplier Final (Procurement Specialist)**:
   - Procurement Specialist mengevaluasi performa calon vendor berdasarkan 4 kriteria terbobot: **Harga, Kualitas, Lead Time, dan Kepatuhan (*Compliance*)** (skala 0–100).
   - Menetapkan satu supplier resmi sebagai **Supplier Final**.
6. **Matriks Approval Manajerial Berdasarkan Total Nilai (WBS 5.5)**:
   - $\le \text{Rp1.000.000} \rightarrow$ **Pak X** (*Managerial Band X*)
   - $> \text{Rp1.000.000 s.d. Rp10.000.000} \rightarrow$ **Pak Y** (*Managerial Band Y*)
   - $> \text{Rp10.000.000} \rightarrow$ **Pak Z** (*Managerial Band Z*)
7. **Penerbitan Dokumen Purchase Order (PO)**:
   - Dibuat otomatis/manual oleh Procurement setelah seluruh approval selesai.
   - Menyertakan nomor PO unik, rincian pesanan, dan halaman cetak profesional (*print-friendly* / simpan ke PDF).
8. **Penerimaan Barang/Jasa & Penanganan Discrepancy (Receiver)**:
   - Receiver di gudang/kantor mencatat penerimaan barang (mendukung **penerimaan bertahap / parsial**).
   - Jika terdapat barang cacat, rusak, atau kurang, Receiver dapat mencatat **Discrepancy**.
   - **Aturan Bisnis (BR-08 / WBS 7.5)**: Status pengadaan **tidak dapat ditutup (*Fulfilled/Closed*)** selama masih ada discrepancy berstatus *Open* atau kuantitas barang belum sepenuhnya diterima.

### 2. Alur Pembatalan (BPMN Flow Pembatalan)
- Requester dapat mengajukan pembatalan sebelum dokumen PO diterbitkan dengan menyertakan alasan tertulis.
- Permintaan ditinjau oleh pihak **Procurement**.
- Jika **Disetujui** $\rightarrow$ status beralih menjadi *Cancelled*.
- Jika **Ditolak** $\rightarrow$ status otomatis dipulihkan ke status sebelumnya (*Restored*) dan proses pengadaan berlanjut tanpa menghapus rekam jejak audit.

### 3. Re-approval Otomatis pada Perubahan Material
- Jika Requester mengubah total nominal atau mengganti supplier usulan setelah proses approval berjalan, sistem secara otomatis mereset status pengadaan kembali ke review awal (Section Head) demi integritas tata kelola anggaran.

---

## Matriks Peran Pengguna (RBAC)

Sistem mengimplementasikan 8 peran pengguna dengan batasan akses di tingkat server (*server-side decorators & queryset filtering*):

| Role | Nama Peran | Wewenang Utama | Batasan |
|---|---|---|---|
| `requester` | Requester | Membuat & merevisi request, mengajukan pembatalan | Hanya dapat melihat & mengedit request miliknya |
| `section_head` | Section Head | Review persetujuan tahap 1 (Approve / Reject) | Hanya memproses request berstatus `pending_section_head` |
| `finance` | Finance Approver | Review anggaran tahap 2 (Approve / Reject) | Hanya memproses request berstatus `pending_finance` |
| `admin_procurement` | Admin Procurement | Verifikasi kelengkapan berkas administrasi | **Tidak bisa final reject**, hanya bisa *Return for Correction* |
| `procurement` | Procurement Specialist | Evaluasi vendor, pilih final supplier, buat PO, putuskan pembatalan | Pengambil keputusan teknis pengadaan |
| `managerial_approver` | Managerial Approver | Approval final sesuai matriks nominal (Band X, Y, Z) | Hanya memproses nominal yang sesuai dengan band jabatannya |
| `receiver` | Receiver (Logistik/Gudang) | Catat penerimaan barang/jasa parsial, catat & selesaikan discrepancy | Hanya memproses PO yang berstatus `open` atau `partially_received` |
| `admin_system` | Admin System / Superuser | Kelola akun, penetapan role pengguna, dan konfigurasi master data | Akses penuh ke aplikasi dan Django Admin `/admin/` |

---

## Prasyarat Sistem

Sebelum melakukan instalasi, pastikan perangkat Anda memiliki perangkat lunak berikut:
* **Python**: Versi 3.10, 3.11, 3.12, atau 3.13
* **pip**: Package installer untuk Python
* **Git**: Version control system
* **Database**:
  - **PostgreSQL** (Direkomendasikan untuk production/staging sesuai PRD).
  - Atau **SQLite** bawaan Django (Dapat digunakan langsung untuk keperluan demonstrasi lokal/pengujian cepat).

---

## Langkah Instalasi

### 1. Clone Repository
```bash
git clone https://github.com/username/procurement-app.git
cd procurement-app
```

### 2. Buat dan Aktifkan Virtual Environment
* **Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```
* **macOS / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment Variables (`.env`)
Salin file `.env.example` menjadi `.env`:
* **Windows (PowerShell)**:
  ```powershell
  Copy-Item .env.example .env
  ```
* **macOS / Linux**:
  ```bash
  cp .env.example .env
  ```

Buka file `.env` dan sesuaikan nilainya. Contoh konfigurasi menggunakan SQLite:
```ini
DEBUG=True
SECRET_KEY=django-insecure-procureflow-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
# Jika menggunakan SQLite bawaan:
DATABASE_URL=sqlite:///db.sqlite3

# Jika menggunakan PostgreSQL:
# DATABASE_URL=psql://postgres:password@127.0.0.1:5432/procureflow_db
```

### 5. Jalankan Migrasi Database
```bash
python manage.py migrate
```

---

## Data Pengguna (User Management)

Untuk mempermudah pengujian dan demonstrasi fungsionalitas seluruh alur pengadaan, tersedia **dua cara** dalam menyiapkan data pengguna:

### Opsi A: Template Akun Siap Pakai (Seeder Data) — *REKOMENDASI*
Aplikasi telah dilengkapi dengan perintah seeder otomatis yang membuat **11 akun pengguna** mencakup seluruh peran, 5 data vendor resmi, serta data pengadaan realistis di setiap tahapan alur.

Jalankan perintah berikut:
```bash
python manage.py seed_dummy_data
```
> **Tips:** Gunakan argumen `--clear` jika Anda ingin mengosongkan transaksi lama dan membuat ulang data simulasi dari awal:
> ```bash
> python manage.py seed_dummy_data --clear
> ```

#### Tabel Akun Template Siap Pakai
Semua akun bawaan berikut menggunakan password default: **`password123`**

| Username | Password | Nama Lengkap | Peran (*Role*) | Keterangan / Band | Cocok Untuk Menguji |
|---|---|---|---|---|---|
| **`requester1`** | `password123` | Budi Santoso | Requester | Divisi IT | Buat request baru, revisi draft, ajukan pembatalan |
| **`requester2`** | `password123` | Siti Nurhaliza | Requester | Divisi Operasional | Melihat request berstatus returned, monitor status |
| **`section_head`** | `password123` | Hendra Wijaya | Section Head | Atasan Pemohon | Antrian approval tahap 1 (*Approve / Final Reject*) |
| **`finance`** | `password123` | Ratna Dewi | Finance Approver | Keuangan | Antrian approval tahap 2 (*Cek Anggaran / Reject*) |
| **`admin_proc`** | `password123` | Dimas Pratama | Admin Procurement | Administrasi | Cek berkas, kembalikan ke pemohon (*Return for Correction*) |
| **`procurement`** | `password123` | Maya Kusuma | Procurement Specialist | Pengadaan | Skoring vendor, pilih final supplier, buat PO, putuskan pembatalan |
| **`manager_x`** | `password123` | Bambang Soediro | Managerial Approver | **Band X** ($\le \text{Rp1.000.000}$) | Approval pengadaan nilai kecil |
| **`manager_y`** | `password123` | Tirto Adhi | Managerial Approver | **Band Y** ($> \text{1jt s.d. 10jt}$) | Approval pengadaan nilai menengah |
| **`manager_z`** | `password123` | Zulkifli Mansyur | Managerial Approver | **Band Z** ($> \text{Rp10.000.000}$) | Approval pengadaan nilai besar / CAPEX |
| **`receiver`** | `password123` | Joko Susilo | Receiver | Petugas Gudang / Logistik | Catat penerimaan parsial, buat & selesaikan discrepancy |
| **`admin_system`**| `password123` | Administrator Sistem | Admin System | Superuser | Kelola akun, grup, master vendor di Django Admin |

---

### Opsi B: Membuat User & Role Baru Secara Manual

Jika Anda ingin membuat akun baru sendiri di luar akun template:

#### Cara 1: Melalui Django Admin UI (Paling Mudah)
1. Buat akun superuser terlebih dahulu jika belum ada:
   ```bash
   python manage.py createsuperuser
   ```
2. Jalankan server dan buka browser ke alamat: `http://127.0.0.1:8000/admin/`.
3. Masuk ke menu **Users** $\rightarrow$ klik **Add User** $\rightarrow$ masukkan username dan password.
4. Masuk ke menu **User profiles** $\rightarrow$ klik **Add User Profile**:
   - Pilih user yang baru saja dibuat.
   - Pilih **Role** yang diinginkan (`Requester`, `Section Head`, `Finance`, `Admin Procurement`, `Procurement`, `Managerial Approver`, `Receiver`, atau `Admin System`).
   - Jika memilih role **Managerial Approver**, tentukan **Managerial band** (`X`, `Y`, atau `Z`).
   - Pastikan opsi **Is active** tercentang.
5. Klik **Save**. Pengguna baru sekarang siap login melalui halaman login utama di `http://127.0.0.1:8000/login/`.

#### Cara 2: Melalui Django Shell
Anda juga dapat membuat user secara programatik via terminal:
```bash
python manage.py shell
```
Kemudian jalankan script berikut:
```python
from django.contrib.auth import get_user_model
from procurement.models import UserProfile

User = get_user_model()

# 1. Buat user auth Django
user = User.objects.create_user(
    username="ahmad_finance",
    email="ahmad@company.com",
    password="password123",
    first_name="Ahmad",
    last_name="Dahlan"
)

# 2. Tautkan UserProfile dengan role yang diinginkan
UserProfile.objects.create(
    user=user,
    role=UserProfile.Role.FINANCE,
    is_active=True
)

print(f"User {user.username} berhasil dibuat!")
```

---

## Menjalankan Aplikasi

Setelah database dimigrasi dan akun pengguna disiapkan, jalankan dev server Django:
```bash
python manage.py runserver
```

Akses aplikasi melalui browser:
* **Halaman Login & Aplikasi**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **Django Admin**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Panduan Skenario Demo & Pengujian

Berikut adalah urutan langkah untuk menguji alur lengkap end-to-end:

### Skenario 1: Pengajuan Permintaan Barang/Jasa
1. Login sebagai **`requester1`** (password: `password123`).
2. Klik tombol **Buat Request**.
3. Isi informasi pokok di kolom kiri (Judul, Tanggal Kebutuhan, Tujuan Pengadaan, Supplier Usulan).
4. Isi rincian barang/jasa di accordion kolom kanan. Coba tambah item baru atau hapus item.
5. Simpan sebagai Draft atau langsung klik **Kirim Pengajuan**. Status pengadaan akan berubah menjadi `Pending Section Head`.

### Skenario 2: Persetujuan Atasan & Keuangan
1. Logout, lalu login sebagai **`section_head`** (password: `password123`).
2. Di dashboard, request dari `requester1` akan muncul di tab **Tugas Saya**.
3. Buka detail request, beri catatan, lalu klik **Setujui Permintaan**. Status berubah menjadi `Pending Finance`.
4. Logout, lalu login sebagai **`finance`** (password: `password123`).
5. Buka detail request, masukkan catatan persetujuan anggaran, lalu klik **Setujui Permintaan**. Status berubah menjadi `Pending Admin Procurement`.

### Skenario 3: Verifikasi Administrasi & Evaluasi Vendor
1. Logout, lalu login sebagai **`admin_proc`** (password: `password123`).
2. Periksa kelengkapan administrasi. Perhatikan bahwa Admin Procurement tidak dapat menolak final; hanya tombol **Verifikasi Lengkap** atau **Kembalikan untuk Koreksi** yang aktif. Klik **Verifikasi Lengkap**. Status berubah menjadi `Pending Supplier Evaluation`.
3. Logout, lalu login sebagai **`procurement`** (password: `password123`).
4. Klik **Evaluasi & Pilih Vendor**. Masukkan skor (0–100) untuk Harga, Mutu, Waktu Pengiriman, dan Kepatuhan. Tetapkan sebagai **Supplier Final**. Status berubah menjadi `Pending Managerial Approval`.

### Skenario 4: Approval Manajerial & Cetak Purchase Order
1. Periksa total nominal pengadaan:
   - Jika $\le \text{Rp1.000.000} \rightarrow$ Login sebagai **`manager_x`**.
   - Jika $\text{Rp1.000.001 s.d. Rp10.000.000} \rightarrow$ Login sebagai **`manager_y`**.
   - Jika $> \text{Rp10.000.000} \rightarrow$ Login sebagai **`manager_z`**.
2. Klik **Setujui Permintaan**. Status berubah menjadi `Approved / PO Created`.
3. Login kembali sebagai **`procurement`**, klik **Terbitkan Dokumen PO**.
4. Klik **Cetak / Simpan PDF** untuk melihat dokumen PO dengan tata letak ringkas dan siap cetak.

### Skenario 5: Penerimaan Parsial & Discrepancy di Gudang
1. Login sebagai **`receiver`** (password: `password123`).
2. Buka Purchase Order yang bersangkutan, klik **Catat Penerimaan**.
3. Masukkan jumlah parsial (misal: pesan 10 unit, terima 4 unit). Status PO berubah menjadi `Partially Received`.
4. Catat adanya kendala (*Discrepancy*) seperti kemasan rusak atau fisik penyok. Status berubah menjadi `Discrepancy Open`.
5. Perhatikan bahwa pengadaan **tidak dapat ditutup** sampai discrepancy diselesaikan (*Resolved*) dan sisa barang diterima lengkap.
6. Selesaikan discrepancy dengan memasukkan solusi, lalu catat penerimaan sisa barang (6 unit). Sistem otomatis menandai status akhir sebagai **`Fulfilled / Closed`**.

### Skenario 6: Alur Pembatalan (*Cancellation*)
1. Login sebagai **`requester1`** pada request yang masih dalam proses (belum ada PO).
2. Klik tombol **Batalkan Request** dan masukkan alasan. Status berubah menjadi `Cancellation Pending`.
3. Login sebagai **`procurement`**. Di antrian pembatalan, lakukan pengujian:
   - Jika **Ditolak** $\rightarrow$ Request otomatis kembali ke status sebelum pengajuan batal.
   - Jika **Disetujui** $\rightarrow$ Request resmi ditutup dengan status `Cancelled`.

---

## Menjalankan Automated Tests

Aplikasi dilengkapi dengan rangkaian pengujian otomatis (*unit tests & integration tests*) yang mencakup seluruh aturan bisnis, validasi otorisasi peran, batasan matriks nominal, dan checklist WBS:

Jalankan perintah pengujian:
```bash
python manage.py test
```

### Hasil Test Suite
```text
Found 32 test(s).
System check identified no issues (0 silenced).
................................
----------------------------------------------------------------------
Ran 32 tests in 7.820s

OK
```

Cakupan pengujian mencakup:
* Proteksi login dan pembatasan akses antarmuka berdasarkan role aktif.
* Filter antrian dashboard spesifik per role pengguna.
* Validasi kalkulasi item, subtotal, dan kuantitas positif.
* **Checklist WBS Sheet 6**:
  - `T-01`: Nominal tepat Rp1.000.000 dialokasikan ke **Pak X**.
  - `T-02`: Nominal Rp1.000.001 dialokasikan ke **Pak Y**.
  - `T-03`: Nominal tepat Rp10.000.000 dialokasikan ke **Pak Y**.
  - `T-04`: Nominal Rp10.000.001 dialokasikan ke **Pak Z**.
  - `T-05`: Pencegahan Finance melakukan approval sebelum Section Head (*out-of-order rejection*).
  - `T-06`: Pembatasan Admin Procurement agar tidak bisa melakukan *final reject*.
* Pembatasan penerbitan PO tanpa supplier final.
* Penerimaan parsial dan penolakan *over-receipt* (penerimaan melebihi pesanan).
* Pemblokiran penutupan pengadaan (*fulfillment*) selama ada *open discrepancy*.
* Pemulihan status saat permohonan pembatalan (*cancellation*) ditolak.
* Reset approval otomatis saat terjadi perubahan nominal atau supplier usulan.
* Pagination per 10 data pada tabel daftar pengadaan.

---

## Struktur Direktori Proyek

```text
procurement-app/
│
├── config/                     # Konfigurasi Proyek Django
│   ├── settings.py             # Pengaturan aplikasi, database, dan security
│   ├── urls.py                 # Root URL configuration
│   └── wsgi.py                 # WSGI entry point
│
├── procurement/                # Aplikasi Utama Procurement
│   ├── management/
│   │   └── commands/
│   │       └── seed_dummy_data.py # Seeder data demo & 11 user role
│   ├── migrations/             # Migrasi skema database
│   ├── templates/              # Django Templates
│   │   ├── procurement/
│   │   │   ├── base.html       # Layout induk aplikasi (navbar, sidebar, brand)
│   │   │   ├── dashboard.html  # Dashboard metrik KPI, grafik Chart.js, antrian tugas
│   │   │   ├── request_form.html # Form 2-kolom & accordion item pengadaan
│   │   │   ├── request_list.html # Daftar pengadaan dengan pagination per 10 data
│   │   │   ├── request_detail.html # Detail pengadaan, approval history, audit log
│   │   │   ├── po_detail.html  # Detail Purchase Order & tracking pemenuhan
│   │   │   └── po_print.html   # Template PO siap cetak & ramah printer/PDF
│   │   └── registration/
│   │       └── login.html      # Halaman autentikasi modern & responsif
│   ├── admin.py                # Konfigurasi Django Admin
│   ├── forms.py                # Formset & form validasi
│   ├── models.py               # Entity models (Request, PO, Receipt, Discrepancy, dll)
│   ├── services.py             # Core business logic, workflow engine, audit trail
│   ├── tests.py                # Automated unit & integration tests
│   ├── urls.py                 # Routing URL modul procurement
│   └── views.py                # Views controller dan visual filtering
│
├── guide/                      # Dokumen Acuan Spesifikasi & Analisis
│   ├── BRD_Procurement_Management_System_Django.docx # Business Requirement Document
│   ├── PRD_Procurement_Management_System_Django.docx # Product Requirement Document
│   ├── Rancangan_UI_ProcureFlow.md                   # Spesifikasi desain antarmuka
│   ├── WBS_Procurement_Management_System.xlsx        # Work Breakdown Structure
│   ├── flow utama.png                                # Diagram BPMN alur utama
│   └── flow pembatalan.png                           # Diagram BPMN pembatalan
│
├── .env.example                # Template konfigurasi environment variables
├── .gitignore                  # File & folder yang diabaikan oleh Git
├── manage.py                   # Script CLI utilitas Django
├── README.md                   # Dokumentasi instalasi, panduan peran, & pengujian
└── requirements.txt            # Daftar pustaka dependensi Python
```

---

## Lisensi & Hak Cipta
Aplikasi ini dikembangkan untuk keperluan pengujian teknis (*Take-Home Assessment / Technical Demonstration*) sistem pengadaan barang dan jasa internal korporasi. Seluruh kode sumber dirancang untuk mudah dipelihara, aman, dan dapat dijalankan secara mandiri.
