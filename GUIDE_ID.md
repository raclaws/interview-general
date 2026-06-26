# INS ATS — Panduan Tim Rekrutmen

## Cara Pakai Panduan Ini

Cari berdasarkan **apa yang mau kamu capai**, bukan berdasarkan halaman. Setiap flow punya tujuan akhir yang jelas.

---

## 1. Buka Lowongan Baru

**Tujuan:** Ada posisi baru yang siap terima kandidat.

Sidebar → Jobs → klik ikon `+` → isi form (Position, Level, BU, Headcount wajib) → Create Job.

Selesai ketika: Job muncul di list dengan status **Open**.

> Recruiter dan Hiring Manager otomatis terisi dari setting BU. Override jika beda.

---

## 2. Masukkan Kandidat ke Sistem

**Tujuan:** Kandidat terdaftar dan siap diproses.

Sidebar → Candidates → klik `+` → pilih Manual Entry → isi Name + Email (wajib), sisanya opsional → Create Candidate.

Selesai ketika: Profil kandidat muncul di list.

> Bisa juga import dari NocoDB jika datanya sudah ada di sana.

---

## 3. Hubungkan Kandidat ke Lowongan (Pipeline)

**Tujuan:** Kandidat resmi masuk proses rekrutmen untuk posisi tertentu.

Buka profil kandidat → scroll ke Pipeline → klik "+ New Opening" → pilih Job → Add.

Selesai ketika: Pipeline muncul di profil kandidat dengan stage **Screening**.

> Alternatif: dari Job detail, klik "+ Add Candidate" untuk arah sebaliknya.

---

## 4. Jadwalkan Interview

**Tujuan:** Interviewer punya link unik untuk submit penilaian.

Buka profil kandidat → di pipeline yang relevan → klik "+ Add Interview" → pilih Template → isi nama interviewer (pisah koma kalau lebih dari satu) → isi tanggal → Create Session.

Selesai ketika: Session muncul di list Interview dengan status **Pending**, setiap interviewer punya link sendiri.

> Salin link: klik ikon 💬 di baris session → di peek panel bisa lihat detail. Atau klik kanan → Copy link.

---

## 5. Bagikan Link Interview

**Tujuan:** Interviewer bisa akses form penilaian.

Buka Session detail → di tabel Interviewers → klik "Copy" di samping nama → kirim link ke interviewer via WA/email.

Selesai ketika: Interviewer mengakses link dan submit form.

> Link sekali pakai — setelah submit, link tidak bisa dipakai lagi.

---

## 6. Assign Technical Test

**Tujuan:** Kandidat dapat link test dan tahu deadline-nya.

Buka Pipeline detail → klik "+ Assign Test" → isi judul + URL test (misal HackerRank) → set deadline jika perlu → Assign Test.

Selesai ketika: Test muncul di pipeline detail, kandidat bisa akses via link.

> Salin link test: di pipeline detail, klik tombol "Link" di baris test.

---

## 7. Geser Stage Kandidat

**Tujuan:** Pipeline menunjukkan progres kandidat yang sebenarnya.

Di halaman Pipelines (list) → klik dropdown stage di baris kandidat → pilih stage baru.

Atau: buka Pipeline detail → ubah dropdown Stage.

Selesai ketika: Stage berubah, activity trail mencatat perpindahan.

> Stage terminal: Hired, Rejected, Withdrawn — artinya proses selesai.

---

## 8. Review Hasil Test (Scoring)

**Tujuan:** Test submission dari kandidat dinilai oleh reviewer.

Sidebar → Review → klik "+ New" → pilih Reviewer Name + Job → Create Batch → salin link review → kirim ke reviewer.

Reviewer membuka link → klik baris kandidat → isi grade + catatan → submit.

Selesai ketika: Semua submission di batch sudah di-score.

---

## 9. Lihat Scorecard

**Tujuan:** Ringkasan skor kandidat dari semua interview yang sudah selesai.

Buka Pipeline detail → klik "Scorecard" di action bar atas.

Selesai ketika: Scorecard menampilkan skor HR + Culture per interviewer dan rata-rata.

> Scorecard otomatis terisi dari session yang completed. Tidak perlu input manual.

---

## 10. Tutup Lowongan

**Tujuan:** Posisi sudah terisi, tidak menerima kandidat baru.

Buka Job detail → klik "Close Job" → konfirmasi.

Selesai ketika: Job tidak muncul lagi di list aktif (tersembunyi di filter "Show closed").

> Bisa dibuka lagi: klik "Reopen Job" kapan saja.

---

## 11. Tambah Catatan / Komentar

**Tujuan:** Konteks atau diskusi tercatat di trail — bisa dibaca tim kapan saja.

Di halaman detail (Job/Pipeline/Session/Candidate) → scroll ke bagian Activity → ketik komentar → Enter.

Atau: di list page, klik ikon 💬 di baris mana saja → peek panel terbuka → ketik komentar → Enter.

Selesai ketika: Komentar muncul di trail dengan timestamp.

> Trail juga mencatat aksi otomatis (stage berubah, session dibuat, job ditutup).

---

## 12. Batalkan Interview / Test

**Tujuan:** Session atau test yang sudah tidak relevan di-cancel agar tidak mengganggu.

Interview: buka Session detail → klik ⊘ (cancel) di action bar → konfirmasi.

Test: buka Pipeline detail → di baris test, klik ⊘ → konfirmasi.

Selesai ketika: Status berubah ke **Cancelled**. Link tidak bisa diakses lagi.

> Cancel tidak bisa di-undo. Kalau salah, buat session/test baru.

---

## 13. Cek Dashboard

**Tujuan:** Tahu apa yang butuh perhatian hari ini tanpa buka satu per satu.

Sidebar → Dashboard.

- **Needs Attention** — interview overdue, test lewat deadline, pipeline 14 hari tidak bergerak
- **Upcoming Interviews** — jadwal interview minggu ini
- **Quick Actions** — shortcut buat session/job/candidate baru

> Klik item di Needs Attention untuk langsung ke halaman yang relevan.

---

## Tips

- **Klik kanan** di baris mana saja untuk aksi cepat (edit, copy link, delete)
- **Peek panel** (ikon 💬) untuk lihat ringkasan + komentar tanpa pindah halaman
- **Filter + Display** di setiap list page untuk cari data spesifik
- **Show completed/closed** — toggle untuk munculkan data yang sudah selesai
- Kalau halaman terasa basi setelah lama ditinggal, akan muncul toast "This page has been updated"
