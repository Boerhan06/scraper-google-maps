# 🗺️ Premium Google Maps Scraper CLI

Selamat datang di **Google Maps Scraper - Premium CLI Edition**! Script ini adalah *automated web scraper* berbasis Python dan Playwright yang dirancang dengan antarmuka terminal (CLI) yang super interaktif, rapi, dan modern.

Bayangkan Anda memiliki asisten robot premium yang akan mengumpulkan data bisnis di Google Maps secara otomatis, lengkap dengan navigasi yang cerdas, visual terminal yang memukau, dan output instan! 🚀

---

## 🎨 Fitur Utama & Keunggulan Visual

* 💬 **Interactive Terminal Prompt**: Tidak perlu lagi mengubah kata kunci secara manual di dalam kode! Cukup jalankan script, dan program akan menyapa serta meminta apa yang ingin bos cari secara interaktif.
* 🔠 **Dynamic 5x5 ASCII Font Engine**: Kata kunci pencarian utama (seperti `HOTEL`, `CAFE`, `SALON`, dll.) akan secara otomatis digambar menjadi huruf blok raksasa neon di terminal Anda.
* 🌈 **ANSI Neon Color Palette**: Dilengkapi dengan ornamen pembatas ganda artistik, penanda proses berwarna neon, dan emoji interaktif untuk memantau proses scraping dengan nyaman.
* 🎴 **Styled Data Cards**: Menampilkan hasil ekstraksi data secara real-time di terminal dalam bentuk kartu informasi terstruktur dengan rating bintang (`⭐`), ulasan, kategori, alamat, telepon, dan jam buka.
* 🛡️ **Resilient Anti-Detachment**: Dibangun menggunakan kombinasi selector cerdas dan simulasi penekanan tombol keyboard global guna menghindari error element lepas (*detachment*) akibat pembaruan dinamis Google Maps.
* 📊 **Double Output Format**: Otomatis menyimpan hasil ke dalam folder `output/` dalam dua format sekaligus:
  * **CSV** (Rapi & siap dibuka di Excel)
  * **JSON** (Tersusun rapi untuk developer / pengolahan data lanjutan)

---

## ⚡ Cara Cepat Menjalankan (Shortcut `run`)

Sekarang bos tidak perlu lagi mengetik perintah panjang `python scraper_google_maps.py`. Cukup buka terminal (PowerShell atau Command Prompt) di folder project ini, lalu ketik:

```powershell
.\run
```
*(Atau cukup ketik `run` jika menggunakan Command Prompt standard)*. Perintah ini akan otomatis memanggil script utama bos!

---

## 🛠️ Panduan Instalasi (Sekali Setup)

Sebelum menjalankan shortcut `run`, pastikan komputer bos sudah disiapkan dengan langkah mudah berikut:

### Step 1️⃣: Install Python (Jika belum punya)
* Download Python 3.8+ di [python.org/downloads](https://www.python.org/downloads/).
* **PENTING:** Saat menginstal di Windows, pastikan **centang kotak "Add python.exe to PATH"** sebelum mengklik *Install Now*.

### Step 2️⃣: Pasang Library Pendukung
Buka PowerShell/Terminal di folder ini, lalu jalankan:
```powershell
pip install -r requirements.txt
```

### Step 3️⃣: Pasang Browser Otomatis (Playwright Chromium)
Jalankan perintah ini sekali untuk mengunduh browser khusus yang akan digunakan program untuk scraping:
```powershell
python -m playwright install chromium
```

---

## 📊 Hasil Output yang Dihasilkan

Setelah proses scraping selesai, data akan otomatis disimpan secara rapi di direktori:
```text
output/
├── google_maps_places.csv      # Format tabel (buka langsung di Excel)
└── google_maps_places.json     # Format JSON terstruktur
```

Setiap data tempat yang dikumpulkan meliputi:
* **Nama Tempat** (Nama bisnis)
* **Rating & Jumlah Ulasan** (⭐ 4.5 / 1,200 ulasan)
* **Kategori Bisnis** (Cafe, Hotel, Restoran, dll.)
* **Alamat Lengkap**
* **Nomor Telepon** (Format internasional)
* **Jam Operasional**
* **Tautan Menu** (Jika tersedia)
* **URL Google Maps** (Tautan langsung ke tempat tersebut)

---

## ⚙️ Kustomisasi Tambahan

Bila ingin mengatur batas kecepatan atau kedalaman pencarian, bos bisa mengubah variabel di bagian atas file `scraper_google_maps.py`:

| Parameter | Deskripsi | Bawaan |
|-----------|-----------|---------|
| `SCROLL_PAUSE_MS` | Jeda waktu (milidetik) setelah melakukan scroll halaman untuk menunggu data baru. | `1500` |
| `MAX_SCROLL_ATTEMPTS` | Batas maksimum pengguliran halaman (safety limit). | `100` |
| `MAX_IDLE_SCROLLS` | Berapa kali scroll kosong berturut-turut tanpa hasil baru sebelum scraping dianggap selesai. | `3` |

---

## ⚠️ Catatan Penting
* Jangan menutup browser Chromium yang terbuka secara otomatis selama proses scraping berjalan. Biarkan program bekerja hingga muncul pesan sukses di terminal.
* Pastikan koneksi internet stabil agar pemuatan peta dan detail bisnis berjalan dengan lancar tanpa kendala timeout.
