# 🗺️ Google Maps Scraper dengan Playwright

## 📌 Apa Itu Program Ini?

Program ini adalah **web scraper otomatis** yang menggunakan Playwright untuk mengekstrak data bisnis dari Google Maps. Bayangkan Anda memiliki asisten yang:

1. **Membuka Google Maps** secara otomatis
2. **Mencari tempat tertentu** (misalnya: "Cafe di Purwakarta")
3. **Mengumpulkan semua hasil** dengan menggulir dan menunggu data dimuat
4. **Mengekstrak informasi detail** dari setiap tempat seperti nama, rating, jam operasional, alamat, dan nomor telepon
5. **Menyimpan hasilnya** dalam format CSV dan JSON yang siap digunakan

Ini sangat berguna untuk **riset pasar, analisis kompetitor, atau membangun database bisnis lokal** tanpa harus mengetik satu per satu! 🚀

---

## 🎯 Fitur Utama

- ✅ **Otomatis mengumpulkan data** dari hasil pencarian Google Maps
- ✅ **Smart scrolling** - terus menggulir hingga semua hasil termuat
- ✅ **Ekstraksi data lengkap:**
  - Nama tempat
  - Rating dan jumlah ulasan
  - Kategori/jenis bisnis
  - Alamat lengkap
  - Jam operasional
  - Nomor telepon
  - Link menu (jika ada)
  - URL Google Maps

- ✅ **Export ke 2 format:**
  - CSV (mudah dibuka di Excel)
  - JSON (mudah untuk processing data)

- ✅ **Error handling** - data yang tidak ditemukan tidak akan membuat program crash

---

## 🚀 Cara Menjalankan

### Step 1️⃣: Siapkan Environment

Buka PowerShell atau Command Prompt di folder project ini, lalu jalankan:

```powershell
pip install -r requirements.txt
```

Ini akan menginstall library yang dibutuhkan:
- **Playwright** - untuk browser automation
- **Pandas** - untuk export data ke CSV/JSON

### Step 2️⃣: Install Chromium Browser

Playwright perlu browser untuk bekerja:

```powershell
python -m playwright install chromium
```

### Step 3️⃣: Jalankan Script

```powershell
python scraper_google_maps.py
```

Script akan:
1. Membuka browser Chromium
2. Masuk ke Google Maps
3. Mencari "Cafe di Purwakarta" (bisa diubah)
4. Menampilkan progress di console
5. Simpan hasil ke folder `output/`

---

## 📊 Output yang Dihasilkan

Setelah script selesai, Anda akan dapat 2 file:

```
output/
├── google_maps_places.csv      # Format tabel (buka di Excel)
└── google_maps_places.json     # Format JSON (untuk developer)
```

Contoh struktur data:
```json
{
  "nama_tempat": "Kopi Kita",
  "rating": "4.5",
  "jumlah_ulasan": "120",
  "kategori": "Cafe",
  "alamat_lengkap": "Jl. Merdeka No.45, Purwakarta",
  "jam_operasional": "08:00 - 22:00",
  "nomor_telepon": "+62-274-1234567",
  "menu": "https://...",
  "tautan_google_maps": "https://maps.google.com/..."
}
```

---

## ⚙️ Kustomisasi

### Mengubah Kata Kunci Pencarian

Edit file `scraper_google_maps.py` dan cari baris ini:

```python
SEARCH_KEYWORD = "Cafe di Purwakarta"
```

Ubah menjadi apa yang Anda inginkan:

```python
SEARCH_KEYWORD = "Restaurant di Jakarta"
# atau
SEARCH_KEYWORD = "Salon kecantikan di Bandung"
```

### Mengatur Kecepatan & Batas Scroll

Di file `scraper_google_maps.py`, Anda bisa ubah parameter ini:

| Parameter | Deskripsi | Default |
|-----------|-----------|---------|
| `SCROLL_PAUSE_MS` | Waktu tunggu (ms) setelah setiap scroll (untuk hasil baru dimuat) | 1500 |
| `MAX_SCROLL_ATTEMPTS` | Batas maksimal jumlah scroll (safety limit) | 100 |
| `MAX_IDLE_SCROLLS` | Berapa kali scroll tanpa hasil baru sebelum berhenti | 3 |

**Contoh:** Jika ingin lebih cepat, kurangi `SCROLL_PAUSE_MS` menjadi 1000. Untuk hasil lebih lengkap, naikkan `MAX_SCROLL_ATTEMPTS` menjadi 150.

```python
SCROLL_PAUSE_MS = 1000          # Lebih cepat
MAX_SCROLL_ATTEMPTS = 150       # Scroll lebih banyak
MAX_IDLE_SCROLLS = 5            # Lebih teliti sebelum berhenti
```

---

## 📋 Requirements

- **Python 3.8+**
- **Playwright** - untuk browser automation
- **Pandas** - untuk export data
- **Windows/Mac/Linux** - kompatibel semua OS

---

## 💡 Tips & Trik

1. **Mempercepat proses:** Kurangi `SCROLL_PAUSE_MS` jika Google Maps sudah responsif
2. **Mendapat hasil lebih banyak:** Naikkan `MAX_SCROLL_ATTEMPTS` sampai 200+
3. **Hemat data:** Jalankan di waktu yang tepat, karena setiap scroll butuh koneksi internet
4. **Backup data:** Simpan CSV/JSON yang sudah di-generate, jangan langsung dihapus

---

## ⚠️ Catatan Penting

- Script ini menggunakan browser automation yang **tidak headless** (terlihat), jadi Anda bisa melihat prosesnya
- Pastikan **koneksi internet stabil** saat menjalankan
- Jangan tutup browser secara paksa, biarkan script menyelesaikan prosesnya
- Beberapa data mungkin kosong jika bisnis tidak memiliki informasi lengkap di Google Maps
