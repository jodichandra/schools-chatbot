# 📚 Schoool Question Generated For 3 SD

Final Project — Chatbot AI berbasis Streamlit untuk membuat soal latihan
anak kelas 3 SD, dari materi PDF yang disediakan. Chatbot hanya menjawab
berdasarkan isi PDF materi (tidak menjawab di luar konteks).

## Fitur

- Halaman utama berisi pilihan mata pelajaran:
  - Bahasa Inggris, Bahasa Indonesia, Matematika → **Coming Soon** (terkunci)
  - Muatan Lokal → **Budaya Adat Minangkabau** (bisa diklik)
- Halaman chatbot untuk mata pelajaran yang dipilih:
  - Tombol link akses materi di bagian atas
  - Jawaban chatbot dibatasi hanya dari isi materi PDF
  - Pesan pertama apa pun dari user akan dibalas dengan template ajakan
    mengetik "ya"
  - Ketik **"ya"** → chatbot membuat soal latihan
  - Ketik **"kunci jawaban"** → chatbot menampilkan kunci jawaban

## Struktur Folder

```
school-question-generator/
├── app.py                          # Aplikasi utama Streamlit
├── requirements.txt                # Dependensi Python
├── materi/
│   └── budaya_minangkabau.pdf      # Taruh PDF materi kamu di sini
└── .streamlit/
    └── secrets.toml.example        # Contoh konfigurasi API key
```

## Cara Menjalankan

1. **Install dependensi**
   ```bash
   pip install -r requirements.txt
   ```

2. **Tambahkan file materi PDF**
   Taruh file PDF "Budaya Adat Minangkabau" di:
   ```
   materi/budaya_minangkabau.pdf
   ```

3. **Atur API Key OpenAI**
   Salin `.streamlit/secrets.toml.example` menjadi `.streamlit/secrets.toml`,
   lalu isi:
   ```toml
   OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```
   (Jangan commit file `secrets.toml` asli ke GitHub.)

4. **Atur link materi**
   Buka `app.py`, ubah variabel `MATERI_LINK` menjadi link materi kamu
   yang sebenarnya (misalnya link Google Drive):
   ```python
   MATERI_LINK = "https://drive.google.com/your-link-here"
   ```

5. **Jalankan aplikasi**
   ```bash
   streamlit run app.py
   ```

## Catatan Pengembangan Lanjutan

- Mata pelajaran lain (Bahasa Inggris, Bahasa Indonesia, Matematika) sudah
  disiapkan tombolnya di halaman utama, tinggal diaktifkan dan diarahkan
  ke halaman chatbot masing-masing dengan materi PDF yang berbeda.
- Untuk menambah mata pelajaran baru, buat materi PDF baru + tambahkan
  fungsi render halaman chatbot serupa `render_chat()`.

## Deliverables Final Project

- [ ] URL repositori GitHub
- [ ] Screenshot User Interface (halaman utama & halaman chatbot)
