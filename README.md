# 🗺️ Premium Google Maps Scraper - Web App Edition

Selamat datang di **Google Maps Scraper - Premium Web App Edition**! Aplikasi ini adalah *automated web scraper* berkinerja tinggi berbasis Python, Playwright, dan Streamlit yang dirancang dengan antarmuka web (UI) modern, interaktif, dan estetik.

Kini Anda dapat mengumpulkan ribuan data prospek bisnis dari Google Maps secara massal langsung melalui web browser, lengkap dengan penemu kontak otomatis (**WhatsApp, Instagram, TikTok**) dari website resmi target! 🚀

---

## 🎨 Fitur Utama & Keunggulan Premium

* 🌐 **Sleek Web Interface (Streamlit UI)**: Antarmuka berbasis web yang indah, responsif, dan mudah digunakan oleh siapa saja tanpa perlu menyentuh kode pemrograman.
* 🔑 **Multi-Location Search**: Masukkan beberapa kata kunci pencarian sekaligus dipisahkan dengan tanda koma (koma). Program akan memprosesnya secara otomatis satu per satu. *(Contoh: `Cafe di Purwakarta Kota, Cafe di Babakancikao`)*.
* 📡 **Live Console Log**: Logger real-time interaktif langsung di halaman web, menampilkan langkah demi langkah yang sedang dikerjakan robot scraper di latar belakang.
* 🔗 **Auto-Social Media & WhatsApp Finder**: Jika bisnis memiliki website resmi, bot akan mengunjungi website tersebut secara instan selama **maksimal 3 detik** (`timeout=3`) untuk menyedot link **Instagram**, **TikTok**, dan nomor chat **WhatsApp** (`wa.me`) target menggunakan Regex canggih!
* ⚡ **Ultra-Fast & Bandwidth Saving**:
  * **Scroll-First Gathering**: Bot mengumpulkan semua tautan detail tempat di panel kiri terlebih dahulu sebelum mengunjungi isinya satu per satu.
  * **Resource Blocking**: Memblokir seluruh aset berat seperti ubin gambar (`image`), file video (`media`), dan file huruf (`font`) saat membuka detail, menghemat bandwidth hingga 70% dan mempercepat pemuatan halaman detail hingga 3x lipat!
  * **Dynamic Waiting**: Bot tidak menggunakan jeda statis. Begitu judul tempat (`h1`) muncul di layar, data langsung disedot secara instan.
* 🧹 **Auto-Deduplication**: Hasil data yang digabungkan dari berbagai kata kunci akan dibersihkan secara otomatis dari data duplikat (berdasarkan nama dan link Google Maps) menggunakan Pandas.
* 📥 **One-Click Download**: Hasil akhir langsung tersaji dalam bentuk tabel interaktif (`st.dataframe`) dan dapat diunduh instan dalam format **CSV** sekali klik.

---

## ⚡ Cara Cepat Menjalankan (Shortcut `run`)

Buka terminal (PowerShell atau Command Prompt) di folder project ini, lalu ketik shortcut super mudah:

```powershell
.\run
```
*(Atau cukup ketik `run` jika menggunakan Command Prompt standard)*. Perintah ini akan otomatis memanggil server Streamlit dan membuka aplikasi web di browser Anda secara otomatis!

---

## 🛠️ Panduan Instalasi (Sekali Setup)

Sebelum menjalankan shortcut `run`, pastikan komputer Anda telah disiapkan dengan langkah mudah berikut:

### Step 1️⃣: Install Python (Jika belum punya)
* Download Python 3.8+ di [python.org/downloads](https://www.python.org/downloads/).
* **PENTING:** Saat menginstal di Windows, pastikan **centang kotak "Add python.exe to PATH"** sebelum mengklik *Install Now*.

### Step 2️⃣: Pasang Library Pendukung
Buka PowerShell/Terminal di folder ini, lalu jalankan:
```powershell
pip install -r requirements.txt
```

### Step 3️⃣: Pasang Browser Otomatis (Playwright Chromium)
Jalankan perintah ini sekali untuk mengunduh browser khusus yang akan digunakan program di latar belakang (headless):
```powershell
python -m playwright install chromium
```

---

## 📊 Hasil Ekstraksi Data yang Dikumpulkan

Setiap data tempat yang berhasil dikumpulkan meliputi:
* **Nama Tempat** (Nama bisnis)
* **Rating & Jumlah Ulasan** (⭐ 4.5 / 1,200 ulasan)
* **Kategori Bisnis** (Cafe, Hotel, Restoran, Kantor, dll.)
* **Alamat Lengkap**
* **Nomor Telepon** (Format internasional)
* **Jam Operasional**
* **Website Resmi**
* **Link Instagram** (Hasil scan otomatis dari website)
* **Link TikTok** (Hasil scan otomatis dari website)
* **Link WhatsApp / wa.me** (Hasil scan otomatis dari website)
* **Tautan Menu** (Jika tersedia)
* **Tautan Google Maps**

---

## ⚙️ Kustomisasi Sidebar Aplikasi Web

Melalui sidebar panel pengaturan pada aplikasi web, Anda dapat menyesuaikan:
* **Batas Maksimal Scroll**: Mengatur seberapa dalam pencarian hasil di panel Google Maps (Safety Limit).
* **Batas Idle (Scroll Kosong)**: Berapa kali scroll tanpa hasil baru berturut-turut sebelum menghentikan pencarian dan lanjut ke ekstraksi detail.

---

## ⚠️ Catatan Penting
* Proses browser Playwright berjalan sepenuhnya di latar belakang (**Headless = True**), sehingga tidak akan ada browser kosong yang mengganggu layar komputer Anda saat Anda sedang bekerja.
* Pastikan koneksi internet Anda lancar agar pemuatan halaman maps dan scanning website eksternal berjalan maksimal tanpa kendala timeout.
