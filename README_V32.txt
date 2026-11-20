CLIPFORGE AI V32 — PAKET APLIKASI + BACKEND

Apa yang ada:
- ClipForge_AI_V32.html : antarmuka aplikasi
- server.py              : backend API scan audio dan export MP4
- requirements.txt       : dependensi Python
- Dockerfile             : image Docker dengan FFmpeg
- render.yaml            : konfigurasi Render Blueprint

PENTING — TIDAK BISA LANGSUNG AKTIF DARI FILE HTML
Fitur scan YouTube memerlukan server internet yang hidup. Paket ini belum di-host. ChatGPT tidak dapat membuat akun hosting atau menerbitkan server atas nama pengguna.

CARA DEPLOY KE RENDER (butuh akun Render dan GitHub):
1. Ekstrak ZIP di komputer.
2. Buat repository GitHub baru, lalu upload SEMUA file dalam folder ini ke root repository.
3. Masuk Render dan pilih New > Blueprint.
4. Hubungkan repository GitHub tadi dan deploy blueprint. Konfigurasi render.yaml akan membuat web service Docker (paket Starter berbayar).
5. Tunggu status Live. Buka URL HTTPS yang diberikan Render.
6. Buka /health pada URL tersebut. Hasil harus menunjukkan ok:true dan ffmpeg:true.
7. Buka URL utama aplikasi, pilih tab URL video, tempel link YouTube publik, tekan Buka Preview YouTube, Tes koneksi server, lalu SCAN VIDEO.
8. Pilih kandidat dan tekan EXPORT CLIP MP4.

CATATAN KOMPATIBILITAS:
- Gunakan hanya video yang Anda miliki atau punya izin untuk diproses. Proses pengambilan video dapat dibatasi oleh YouTube, hak cipta, wilayah, usia, atau perubahan teknis YouTube.
- Video privat, live, berbayar, atau dibatasi mungkin gagal diproses.
- Analisis mencari puncak intensitas audio; ini bukan penilaian AI tentang isi, konteks, atau potensi viral.
- Server memerlukan internet, FFmpeg, ruang disk dan RAM/CPU yang cukup. Render Starter berbayar; paket gratis/instance tidur dapat tidak cocok untuk proses video panjang.
- Export YouTube menghasilkan MP4 potongan video. Subtitle editor dan file SRT tersedia di antarmuka; subtitle yang diketik belum dibakar ke video hasil export YouTube.
- Belum ada hosting yang disiapkan. Keberhasilan akhir harus diverifikasi pada akun hosting milik pengguna.

PEMECAHAN MASALAH:
- Jika /health tidak terbuka: periksa status deploy dan log Render.
- Jika ffmpeg:false: deploy ulang image Docker.
- Jika scan gagal: cek log server; video mungkin tidak dapat diakses dari server atau perlu versi yt-dlp terbaru.
- Jangan bagikan URL rahasia, token, atau kredensial hosting di chat.
