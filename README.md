# WhatsApp Google Drive Extractor

Script Python untuk mengunduh (sync) file backup WhatsApp (seperti database `msgstore.db.cryptXX` dan media) langsung dari Google Drive ke komputer atau HP (Termux).

## ✨ Fitur
- **Info**: Melihat metadata backup (jumlah pesan, ukuran, versi WA).
- **List**: Melihat daftar semua file yang ada di dalam backup.
- **Sync**: Mengunduh semua file secara otomatis (mendukung resume jika terputus).
- **Multiplatform**: Berjalan di Windows (CMD/PowerShell), Linux, dan Android (Termux).

---

## 🚀 Cara Instalasi

### 1. Prasyarat
Pastikan Anda sudah menginstal Python 3.

### 2. Clone Repositori
```bash
git clone [https://github.com/123tool/WhatsApp-Google-Drive-Extractor.git]
cd Whatsapp-Google-Drive-Extractor
python wa_drive_extractor.py
