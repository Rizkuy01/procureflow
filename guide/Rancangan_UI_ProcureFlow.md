# Rancangan UI ProcureFlow

## 1. Tujuan Dokumen

Dokumen ini menjadi acuan perbaikan antarmuka aplikasi Procurement Management System
(`ProcureFlow`) sebelum implementasi kode dilakukan. Rancangan mempertahankan business
flow yang sudah berjalan dan berfokus pada:

- keterbacaan informasi;
- pengurangan kebingungan berdasarkan role;
- penonjolan pekerjaan yang harus ditindaklanjuti;
- konsistensi komponen dan status;
- penggunaan desktop dan mobile;
- aksesibilitas dasar;
- kesiapan implementasi bertahap.

Dokumen ini tidak mengubah aturan bisnis, hak akses, status database, atau endpoint
yang sudah ada. Perubahan perilaku hanya boleh dilakukan jika disetujui sebagai
perubahan business requirement.

## 2. Baseline Aplikasi Saat Ini

Template utama saat ini menggunakan:

- [`base.html`](../procurement/templates/procurement/base.html) sebagai layout global;
- [`dashboard.html`](../procurement/templates/procurement/dashboard.html) sebagai dashboard;
- [`app.css`](../procurement/static/procurement/css/app.css) sebagai stylesheet bersama;
- dashboard queue yang sudah difilter berdasarkan role;
- halaman request, approval, supplier evaluation, PO, receipt, milestone,
  discrepancy, cancellation, dan PO print-friendly.

Rancangan berikut memperbaiki presentasi visual tanpa mengganti flow URL dan service
utama.

## 3. Prinsip Desain

### 3.1 Action-oriented

Pengguna harus dapat menjawab tiga pertanyaan dalam waktu singkat:

1. Saya sedang berperan sebagai apa?
2. Pekerjaan apa yang harus saya lakukan?
3. Apa dampak atau langkah berikutnya?

### 3.2 Status selalu terlihat

Setiap request dan PO menampilkan status dalam bentuk badge dengan teks yang jelas.
Warna hanya sebagai pendukung, bukan satu-satunya indikator.

### 3.3 Progressive disclosure

Informasi ringkas ditampilkan di dashboard dan daftar. Detail lengkap ditampilkan
di halaman detail atau panel yang dapat dibuka.

### 3.4 Konsisten

Label tombol, jarak, warna status, format nominal, breadcrumb, dan struktur halaman
harus sama di seluruh modul.

### 3.5 Aman secara visual

Tombol yang mengubah status, membatalkan request, atau menyelesaikan discrepancy
harus memiliki label tindakan yang eksplisit dan tidak disamarkan sebagai link biasa.

### 3.6 Responsive dan keyboard-friendly

Semua fungsi utama harus tetap dapat digunakan pada layar kecil dan melalui keyboard.
Fokus keyboard harus terlihat, label form harus terhubung dengan input, dan warna
teks harus memiliki kontras yang memadai.

## 4. Arah Visual

### 4.1 Gaya

Gaya yang digunakan adalah **modern soft**:

- latar abu-abu kebiruan yang lembut;
- card putih dengan border tipis;
- radius sedang, tidak berlebihan;
- aksen biru untuk primary action;
- warna status pastel;
- tipografi sederhana dan formal;
- ruang kosong cukup untuk memisahkan kelompok informasi.

### 4.2 Token visual

| Token | Penggunaan | Nilai awal |
|---|---|---|
| `--color-ink` | teks utama | `#172033` |
| `--color-muted` | teks sekunder | `#64748b` |
| `--color-background` | latar aplikasi | `#f6f8fc` |
| `--color-surface` | card dan panel | `#ffffff` |
| `--color-primary` | tombol utama, link | `#2563eb` |
| `--color-primary-dark` | hover/fokus | `#1d4ed8` |
| `--color-success` | approved/fulfilled/resolved | `#047857` |
| `--color-warning` | pending/needs action | `#a16207` |
| `--color-danger` | rejected/cancelled | `#b91c1c` |
| `--color-info` | informasi netral | `#1e40af` |
| `--space-1` sampai `--space-6` | jarak konsisten | 4–32px |
| `--radius-sm/md/lg` | radius kontrol/card | 6/10/14px |

Nilai final dapat disesuaikan setelah review visual, tetapi semua halaman harus
menggunakan token bersama dan tidak menambahkan warna acak per template.

## 5. Struktur Navigasi Global

### 5.1 Desktop

```text
┌─────────────────────────────────────────────────────────────────────┐
│ ProcureFlow                         User · Role       Keluar         │
├──────────────────┬──────────────────────────────────────────────────┤
│ Dashboard        │                                                  │
│ Requests         │                 Area halaman                     │
│ Supplier         │                                                  │
│ Purchase Orders  │                                                  │
│ Fulfillment      │                                                  │
│ Admin (jika ada) │                                                  │
└──────────────────┴──────────────────────────────────────────────────┘
```

- Sidebar lebar sekitar 232–264px.
- Item aktif memiliki background aksen lembut dan indikator kiri.
- Topbar tetap terlihat saat halaman panjang.
- Konten memiliki lebar maksimum agar tabel tidak terlalu melebar.
- Sidebar tidak menampilkan menu yang tidak relevan dengan role.

### 5.2 Mobile

```text
┌────────────────────────────────┐
│ ☰  ProcureFlow       User      │
├────────────────────────────────┤
│          Konten                │
└────────────────────────────────┘
```

- Sidebar berubah menjadi drawer.
- Tombol menu harus memiliki label aksesibilitas.
- Drawer dapat ditutup dengan tombol close, klik area luar, atau tombol Escape.
- Aksi utama tetap terlihat di bagian atas halaman.
- Navigasi tidak boleh mengandalkan hover.

### 5.3 Matriks menu berdasarkan role

| Menu | Requester | Section Head | Finance | Admin Procurement | Procurement | Manager | Receiver | Admin/Superuser |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dashboard | Ya | Ya | Ya | Ya | Ya | Ya | Ya | Ya |
| Request saya/yang terlihat | Ya | Ya | Ya | Ya | Ya | Ya | Opsional | Ya |
| Approval queue | - | Ya | Ya | Ya | Opsional | Ya | - | Ya |
| Supplier evaluation | - | - | - | - | Ya | - | - | Ya |
| Purchase Order | Terbatas | Terbatas | Terbatas | Ya | Ya | Terbatas | Ya | Ya |
| Penerimaan | - | - | - | - | Terbatas | - | Ya | Ya |
| Discrepancy | - | - | - | - | Ya | - | Ya | Ya |
| User/supplier admin | - | - | - | - | - | - | - | Ya |

Menu adalah bantuan navigasi, bukan pengganti validasi permission di server.

## 6. Komponen Bersama

### 6.1 Page header

Struktur:

```text
Breadcrumb
Judul halaman                         Primary action
Deskripsi singkat/status               Secondary action
```

Aturan:

- Judul menggunakan satu `h1`.
- Breadcrumb menggunakan link untuk halaman sebelumnya.
- Primary action hanya satu per halaman.
- Status berada dekat judul jika halaman mewakili satu entity.

### 6.2 Status badge

Format label harus menggunakan label bisnis, bukan nilai database.

| Kelompok status | Gaya |
|---|---|
| Draft | neutral abu-abu |
| Pending approval/evaluation | warning kuning |
| Returned for correction | orange |
| Approved/open | info biru |
| Partially received | purple/biru tua |
| Fulfilled/resolved | success hijau |
| Rejected/cancelled | danger merah |
| Cancellation pending | warning merah muda |

Badge tetap memuat teks, misalnya `Pending Finance`, bukan hanya titik berwarna.

### 6.3 Button

- Primary: tindakan utama, misalnya `Ajukan request`, `Buat PO`.
- Secondary: navigasi atau tindakan pendukung, misalnya `Lihat detail`.
- Danger: pembatalan atau tindakan yang tidak mudah dibatalkan.
- Disabled: hanya digunakan jika alasan dapat dijelaskan melalui helper text.
- Tombol form harus memiliki state submit agar tidak diklik berulang.

### 6.4 Alert dan message

Setiap pesan harus:

- menjelaskan hasil tindakan;
- menyebutkan langkah berikutnya jika gagal;
- menggunakan warna dan ikon opsional;
- dapat dibaca screen reader;
- tidak menghilang terlalu cepat untuk error validasi.

### 6.5 Table dan mobile card

Desktop menggunakan tabel untuk data komparatif. Pada mobile:

- tabel boleh horizontal scroll jika kolom penting masih harus dibandingkan; atau
- row diubah menjadi card dengan pasangan label-value;
- nomor request dan status harus selalu berada di area pertama card;
- tombol aksi tidak boleh keluar dari viewport.

### 6.6 Empty state

Empty state memiliki:

1. judul singkat;
2. penjelasan;
3. primary action jika relevan.

Contoh:

```text
Tidak ada pekerjaan yang perlu ditindaklanjuti
Semua queue untuk role Anda saat ini sudah kosong.
```

## 7. Tahap Implementasi UI

Implementasi dilakukan dalam lima tahap. Setiap tahap harus lulus validasi sebelum
masuk tahap berikutnya.

---

## Tahap UI 1 — Layout Global dan Dashboard

### Tujuan

Mengubah dashboard dari halaman sambutan menjadi workspace utama pengguna.

### File target

- `procurement/templates/procurement/base.html`
- `procurement/templates/procurement/dashboard.html`
- `procurement/static/procurement/css/app.css`
- `procurement/views.py` untuk data ringkasan yang benar-benar diperlukan

### Layout

Desktop:

```text
Topbar
├── Sidebar
└── Main content
    ├── Welcome header + primary action
    ├── Summary cards
    ├── Action queue
    └── Recent requests
```

Mobile:

```text
Compact topbar
├── Welcome header
├── Horizontal summary cards
├── Action queue cards
└── Recent request cards
```

### Dashboard detail

#### Welcome header

Menampilkan:

- `Selamat datang, {username}`;
- role aktif;
- tanggal atau konteks workspace secara opsional;
- tombol `+ Buat request` hanya jika user boleh membuat request.

#### Summary cards

Minimal empat card:

1. `Perlu tindakan`
2. `Menunggu approval`
3. `PO aktif`
4. `Selesai`

Card menampilkan:

- angka;
- label;
- deskripsi singkat;
- link/filter yang sesuai jika tersedia.

Angka harus dihitung dari queryset yang konsisten dengan queue dan permission user.
Jangan menampilkan angka global kepada user biasa.

#### Action queue

Kolom desktop:

| Nomor | Judul | Requester | Status | Total | Aksi |
|---|---|---|---|---:|---|

Prioritas urutan:

1. request yang membutuhkan tindakan;
2. request paling lama menunggu;
3. request terbaru.

Jika queue kosong, gunakan empty state. Jika lebih dari batas tampilan, tampilkan
link `Lihat semua`.

#### Recent requests

Menampilkan request terbaru yang boleh dilihat user. Bagian ini tidak boleh
menggantikan action queue.

### Acceptance criteria

- User dapat memahami role dan queue dalam satu layar.
- Queue requester tidak menampilkan request user lain.
- Queue approver hanya menampilkan status yang relevan.
- Superuser dapat melihat data sesuai kebijakan admin.
- Dashboard tetap dapat digunakan pada lebar sekitar 360px.
- Tidak ada horizontal overflow pada layout utama.
- Link ke detail request tetap bekerja.
- Existing dashboard dan access tests tetap lulus.

---

## Tahap UI 2 — Request dan Approval

### Tujuan

Membuat pembuatan, pengeditan, detail, dan approval request lebih terstruktur.

### Halaman yang diperbaiki

- request list;
- request create/edit;
- request detail;
- approval decision panel.

### Request list

Fitur visual:

- filter status;
- pencarian nomor/judul;
- filter rentang tanggal jika dibutuhkan;
- tabel desktop dan card mobile;
- status badge;
- total dengan format Rupiah;
- empty state dan hasil pencarian kosong.

Filter harus mempertahankan permission queryset server. Filter UI tidak boleh
memungkinkan user mengakses request yang tidak terlihat pada server.

### Request form

Kelompok field:

#### Informasi utama

- Judul pengadaan
- Tujuan
- Tanggal kebutuhan
- Supplier usulan

#### Item pengadaan

Setiap item berupa card atau row dengan:

- deskripsi;
- jenis: Goods/Service;
- quantity;
- unit;
- estimasi harga satuan;
- total baris yang dihitung.

Bagian bawah menampilkan `Total estimasi` secara menonjol.

Pesan bahwa perubahan nominal atau supplier setelah approval dapat menyebabkan
approval diulang harus ditampilkan sebagai helper text sebelum user menyimpan.

### Request detail

Struktur:

```text
Breadcrumb
Header: nomor, judul, status
Action bar
├── Ringkasan
├── Detail kebutuhan
├── Item dan total
├── Approval progress/timeline
├── Supplier evaluation
├── Cancellation panel
└── PO/fulfillment panel
```

### Approval progress

Tampilkan langkah:

```text
Section Head → Finance → Admin Procurement
→ Supplier Evaluation → Managerial Approval → PO
```

Setiap langkah memiliki state:

- completed;
- current;
- waiting;
- returned/rejected;
- not applicable.

Timeline audit tetap ditampilkan di bawah progress agar detail actor, waktu, dan
komentar tidak hilang.

### Approval panel

Panel hanya muncul untuk role dan status yang sesuai. Panel berisi:

- status yang sedang menunggu;
- penjelasan tanggung jawab role;
- pilihan keputusan;
- komentar;
- tombol konfirmasi;
- peringatan jika keputusan menolak atau mengembalikan.

Requester tidak boleh melihat tombol approval aktif hanya karena dapat membuka
detail request.

### Acceptance criteria

- User dapat membedakan informasi request dan tindakan approval.
- Tahap aktif terlihat tanpa membaca seluruh timeline.
- Nominal total mudah ditemukan.
- Perubahan request menjelaskan konsekuensi approval ulang.
- Form menampilkan error dekat field yang bermasalah.
- Approval action tidak dapat dikirim dua kali secara tidak sengaja.

---

## Tahap UI 3 — Supplier dan Purchase Order

### Tujuan

Membuat evaluasi supplier, penetapan supplier final, dan PO mudah dibandingkan
serta dipahami.

### Supplier evaluation

Halaman terdiri dari:

1. ringkasan request;
2. form skor supplier;
3. tabel perbandingan supplier;
4. supplier dengan skor tertinggi;
5. catatan evaluator.

Tabel:

| Supplier | Harga | Kualitas | Lead time | Compliance | Total | Evaluator |
|---|---:|---:|---:|---:|---:|---|

Total score harus diberi penjelasan bahwa saat ini menggunakan bobot sama, apabila
business rule belum menetapkan bobot berbeda.

### Supplier selection

- Supplier yang belum dievaluasi tidak muncul sebagai pilihan final.
- Supplier terpilih diberi highlight.
- Sebelum submit, tampilkan ringkasan supplier dan score.
- Perubahan supplier final setelah approval harus mengikuti aturan business service.

### PO detail

Header:

- nomor PO;
- status;
- supplier;
- request terkait;
- tombol `Print / PDF`.

Isi:

- ringkasan supplier dan requester;
- item order;
- quantity order;
- quantity diterima;
- sisa;
- progress fulfillment;
- milestone jasa;
- discrepancy.

### PO print page

Halaman print-friendly harus:

- tidak menampilkan sidebar/topbar aplikasi;
- memiliki header dokumen;
- memiliki nomor PO dan tanggal;
- memiliki supplier dan requester;
- menampilkan tabel item dan total;
- memiliki tujuan pengadaan;
- menyembunyikan tombol ketika dicetak;
- dapat disimpan sebagai PDF dari browser.

### Acceptance criteria

- Evaluator dapat membandingkan supplier tanpa membuka banyak halaman.
- Supplier final yang dipilih terlihat jelas.
- PO dapat dibaca pada layar dan kertas A4.
- Total PO konsisten dengan item request.
- Tombol print tidak muncul pada hasil cetak.

---

## Tahap UI 4 — Fulfillment, Milestone, dan Discrepancy

### Tujuan

Membantu Receiver dan Procurement memantau progres penerimaan secara operasional.

### Progress fulfillment

Untuk goods:

```text
Diterima 6 / 10 unit
██████████░░░░░░ 60%
Sisa 4 unit
```

Untuk service:

```text
Milestone selesai 2 / 4
████████░░░░░░░░ 50%
```

Progress harus memiliki angka, bukan warna saja.

### Receipt form

Field:

- item PO;
- quantity diterima;
- catatan penerimaan.

Tampilkan:

- quantity order;
- quantity sudah diterima;
- quantity tersisa;
- batas maksimum penerimaan.

Jika quantity melebihi sisa, error harus menjelaskan angka maksimum yang boleh
dimasukkan.

### Milestone

Setiap milestone menampilkan:

- nama;
- due date;
- status;
- tanggal selesai;
- catatan;
- tombol `Tandai selesai` jika belum selesai.

Milestone terlambat diberi label teks `Terlambat`, bukan hanya warna merah.

### Discrepancy

Panel discrepancy menampilkan:

- status open/resolved;
- deskripsi;
- receipt terkait jika ada;
- tanggal dibuat;
- pihak yang menyelesaikan;
- catatan penyelesaian.

Discrepancy open harus memiliki visual peringatan dan menjelaskan bahwa status
fulfillment dapat tertahan.

### Acceptance criteria

- Receiver mengetahui item dan sisa quantity sebelum mencatat penerimaan.
- Partial receipt terlihat jelas.
- Service milestone memiliki progres yang mudah dipahami.
- Discrepancy open tidak tertukar dengan discrepancy resolved.
- Tindakan resolve memiliki input catatan wajib.

---

## Tahap UI 5 — Cancellation, Admin, dan Polish

### Tujuan

Menyelesaikan konsistensi visual seluruh flow dan menutup detail pengalaman pengguna.

### Cancellation

Panel cancellation menampilkan:

- alasan;
- requester;
- waktu pengajuan;
- status keputusan;
- reviewer;
- waktu review;
- catatan atau alasan keputusan.

Tombol pembatalan menggunakan warna danger dan konfirmasi yang eksplisit:

```text
Request belum memiliki PO. Setelah disetujui, request akan berstatus Cancelled.
Lanjutkan pengajuan pembatalan?
```

### Admin

Jika halaman admin custom dibuat:

- user ditampilkan sebagai tabel;
- role dan status aktif menggunakan badge;
- form role menggunakan pilihan yang jelas;
- perubahan role memiliki pesan sukses/error;
- audit perubahan role dipertimbangkan sebagai tahap terpisah.

### Accessibility pass

Checklist:

- semua input memiliki label;
- tombol icon memiliki accessible name;
- fokus keyboard terlihat;
- heading berurutan;
- warna memiliki kontras;
- error tidak hanya ditandai warna;
- tabel memiliki header;
- mobile drawer dapat ditutup dengan Escape.

### Performance pass

- Hindari query tambahan dari template untuk setiap row.
- Gunakan `select_related`/`prefetch_related` sesuai kebutuhan view.
- Batasi queue dashboard.
- Jangan memuat data yang tidak dipakai di halaman.

### Acceptance criteria

- Semua halaman memakai header, button, badge, alert, dan spacing yang konsisten.
- Tidak ada halaman inti yang tampak berbeda tanpa alasan.
- Flow utama dapat diselesaikan tanpa kebingungan navigasi.
- UI tidak mengubah permission atau business logic.

## 8. State dan Kondisi yang Wajib Dirancang

Setiap halaman harus memiliki tampilan untuk kondisi berikut:

| Kondisi | Tampilan |
|---|---|
| Data tersedia | konten normal |
| Data kosong | empty state |
| Form pertama kali dibuka | helper text dan field kosong |
| Validasi gagal | error dekat field dan ringkasan bila perlu |
| Permission ditolak | pesan akses dan redirect aman |
| Entity tidak ditemukan | halaman 404 standar |
| Submit berhasil | success message dan redirect yang jelas |
| Submit sedang diproses | tombol disabled/loading |
| Queue banyak | pagination atau link lihat semua |
| Mobile sempit | card/scroll tanpa memotong aksi |

## 9. Aturan Format Data

- Nominal: `Rp 1.250.000,00` atau format Rupiah konsisten yang dipilih saat
  implementasi.
- Tanggal: `dd/mm/yyyy` untuk tampilan Indonesia.
- Waktu: `dd/mm/yyyy HH:mm` jika waktu diperlukan.
- Quantity: tampilkan unit, misalnya `4 unit` atau `2 milestone`.
- Nomor entity: selalu dapat diklik jika user memiliki akses.
- Nilai kosong: gunakan `-`, bukan `None`, string kosong, atau layout kosong.

## 10. Rencana Perubahan Teknis

### Fase A — CSS dan token

- rapikan token warna, spacing, radius, dan shadow;
- tambahkan class layout sidebar/topbar;
- tambahkan badge variants;
- tambahkan table/card responsive utilities;
- pertahankan class lama selama masa transisi.

### Fase B — Base template

- ubah struktur header menjadi topbar + sidebar;
- tambahkan blok menu role-aware;
- tambahkan menu toggle mobile;
- pertahankan CSRF logout dan semua URL existing.

### Fase C — Dashboard view/template

- pertahankan queue permission;
- tambahkan queryset summary yang terukur;
- tampilkan action queue dan recent requests;
- tambahkan empty state.

### Fase D — Halaman domain

- request dan approval;
- supplier dan PO;
- fulfillment dan exception;
- cancellation dan admin.

### Fase E — Validasi

- Django `check`;
- seluruh unit/integration test;
- test setiap role;
- browser check pada desktop dan mobile;
- print check PO;
- accessibility manual pass.

## 11. Strategi Testing UI

### Test server/view

- dashboard anonymous redirect ke login;
- requester hanya melihat request sendiri;
- role queue hanya menampilkan status yang sesuai;
- user tanpa profile aktif tidak mendapat menu role;
- detail dan PO print menerapkan akses yang benar.

### Test template

- status label tampil;
- empty state tampil;
- tombol hanya tampil pada role yang benar;
- nominal dan tanggal terformat;
- print view tidak memuat navigasi aplikasi.

### Test responsive manual

Ukuran minimum:

- 360 × 800;
- 768 × 1024;
- 1280 × 800.

Skenario:

1. membuka dashboard;
2. membuka request detail;
3. mengisi form request;
4. melakukan approval;
5. membuka PO;
6. mencetak PO.

## 12. Definition of Done UI

Satu tahap dianggap selesai apabila:

- rancangan tahap tersebut telah diterapkan tanpa mengubah business rule;
- tidak ada error Django system check;
- test existing tetap lulus;
- test baru untuk state/permission utama tersedia;
- desktop dan mobile tidak memiliki layout rusak;
- empty, error, success, dan permission state telah ditangani;
- file terkait terdokumentasi;
- tidak ada duplicate style yang seharusnya menjadi komponen bersama.

## 13. Urutan Implementasi yang Disepakati

Urutan kerja:

1. Tahap UI 1 — Layout global dan dashboard.
2. Tahap UI 2 — Request dan approval.
3. Tahap UI 3 — Supplier dan PO.
4. Tahap UI 4 — Fulfillment, milestone, dan discrepancy.
5. Tahap UI 5 — Cancellation, admin, accessibility, dan polish.
6. Notifikasi internal setelah UI inti stabil.

Notifikasi sengaja ditempatkan setelah UI inti agar komponen alert, badge, queue,
dan user context sudah konsisten ketika notifikasi ditambahkan.

