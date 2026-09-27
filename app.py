"""
School Question Generated For 3 SD
Final Project - Chatbot Pembuat Soal Latihan Berbasis Materi PDF Upload User (OpenAI API)

Topik/materi TIDAK dikunci ke satu mata pelajaran tertentu.
Soal dan jawaban dibuat berdasarkan isi PDF yang diupload user, apa pun topiknya.

Alur:
1. Halaman Home -> (Upload Materi)
2. Halaman Upload -> user upload PDF materi sendiri (maksimal 5 halaman)
3. Halaman Chat -> tanya jawab / minta dibuatkan soal berdasarkan materi yang diupload
"""

import os
import json

import streamlit as st
import pdfplumber
from openai import OpenAI


# ============================================================
# KONFIGURASI
# ============================================================
MODEL_NAME = "gpt-4o-mini"
MAX_PDF_PAGES = 5

SOAL_TRIGGER_KEYWORDS = {
    "ya", "iya", "y", "ok", "oke", "siap", "boleh", "mau", "yes",
    "buat soal", "buatkan soal", "soal latihan", "kuis", "quiz",
}


# ============================================================
# UTIL: OPENAI CLIENT
# ============================================================
def get_openai_client() -> OpenAI:
    api_key = None
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    api_key = api_key or os.environ.get("OPENAI_API_KEY")

    if not api_key:
        st.error(
            "OPENAI_API_KEY belum diatur. Tambahkan di file "
            "`.streamlit/secrets.toml` (lihat secrets.toml.example) atau "
            "sebagai environment variable."
        )
        st.stop()

    return OpenAI(api_key=api_key)


# ============================================================
# UTIL: BACA PDF YANG DIUPLOAD USER
# ============================================================
def read_uploaded_pdf(uploaded_file, max_pages: int = MAX_PDF_PAGES):
    """
    Membaca PDF yang diupload user.
    Return (materi_text, num_pages) jika valid,
    atau (None, num_pages) jika melebihi batas halaman.
    """
    uploaded_file.seek(0)
    with pdfplumber.open(uploaded_file) as pdf:
        num_pages = len(pdf.pages)
        if num_pages > max_pages:
            return None, num_pages

        text_parts = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)

    return "\n".join(text_parts), num_pages


# ============================================================
# GENERATE SOAL (topik mengikuti isi PDF, TIDAK di-hardcode)
# ============================================================
def generate_quiz(materi_text: str, n_soal: int = 5):
    client = get_openai_client()

    system_prompt = f"""Kamu adalah guru SD kelas 3 yang membuat soal latihan.
Topik soal HARUS mengikuti isi MATERI PDF yang diberikan di bawah ini, apa pun topiknya.
Gunakan HANYA informasi dari MATERI tersebut, jangan menambah informasi dari luar materi.
Bahasa harus sederhana, sesuai untuk anak kelas 3 SD.

Buat {n_soal} soal pilihan ganda (A-D) berdasarkan MATERI berikut.

Balas HANYA dalam format JSON persis seperti ini, tanpa teks tambahan apa pun:
{{
  "topik": "judul singkat topik materi ini",
  "soal": [
    {{"nomor": 1, "pertanyaan": "...", "pilihan": {{"A": "...", "B": "...", "C": "...", "D": "..."}}}}
  ],
  "kunci_jawaban": [
    {{"nomor": 1, "jawaban": "A", "penjelasan": "..."}}
  ]
}}

MATERI:
{materi_text}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": system_prompt}],
        temperature=0.5,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw, "Kunci jawaban tidak tersedia karena format soal tidak sesuai. Coba minta buat soal lagi."

    topik = data.get("topik", "").strip()
    soal_list = sorted(data.get("soal", []), key=lambda s: s.get("nomor", 0))
    kunci_list = sorted(data.get("kunci_jawaban", []), key=lambda k: k.get("nomor", 0))

    judul_soal = f"📝 **Soal Latihan - {topik}**" if topik else "📝 **Soal Latihan**"
    quiz_lines = [judul_soal, ""]
    for s in soal_list:
        quiz_lines.append(f"**{s.get('nomor')}. {s.get('pertanyaan')}**")
        pilihan = s.get("pilihan", {})
        for opt, text in sorted(pilihan.items(), key=lambda pair: pair[0]):
            quiz_lines.append(f"- **{opt}.** {text}")
        quiz_lines.append("")
    quiz_text = "\n".join(quiz_lines).strip()

    answer_lines = ["🔑 **Kunci Jawaban**", ""]
    for k in kunci_list:
        line = f"- **{k.get('nomor')}.** {k.get('jawaban')}"
        if k.get("penjelasan"):
            line += f" — {k.get('penjelasan')}"
        answer_lines.append(line)
    answer_text = "\n".join(answer_lines).strip()

    return quiz_text, answer_text


# ============================================================
# CHAT UMUM (topik mengikuti isi PDF, dibatasi hanya pada materi)
# ============================================================
def grounded_chat(materi_text: str, history: list, user_input: str) -> str:
    client = get_openai_client()

    system_prompt = f"""Kamu adalah chatbot ramah untuk siswa kelas 3 SD.
Topik chatbot ini MENGIKUTI isi MATERI PDF yang diupload user di bawah ini, apa pun isinya
(bisa pelajaran apa saja, bukan topik tertentu yang tetap).

ATURAN PENTING:
1. Kamu HANYA boleh menjawab berdasarkan MATERI di bawah ini.
2. Jika pertanyaan user tidak berkaitan dengan materi ini, tolak dengan sopan
   dan arahkan user untuk meminta dibuatkan soal latihan dari materi ini.
3. Gunakan bahasa sederhana dan ramah, sesuai untuk anak kelas 3 SD.

MATERI:
{materi_text}
"""

    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-6:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.4,
    )
    return response.choices[0].message.content


# ============================================================
# STATE HELPERS
# ============================================================
def init_state():
    st.session_state.setdefault("page", "home")            # home -> upload -> chat
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("current_answer_text", None)
    st.session_state.setdefault("materi_text", None)
    st.session_state.setdefault("materi_filename", None)


def reset_chat_state():
    st.session_state.messages = []
    st.session_state.current_answer_text = None


def reset_materi_state():
    st.session_state.materi_text = None
    st.session_state.materi_filename = None
    reset_chat_state()


# ============================================================
# HALAMAN: HOME
# ============================================================
def render_home():
    st.title("📚 Schoool Question Generated")
    st.write("Selamat datang! Pilih menu untuk membuat soal latihan.")

    st.subheader("Muatan Lokal")
    st.caption("Upload materi PDF-mu sendiri, soal dan jawaban akan mengikuti isi materi tersebut.")
    if st.button("📄 Upload Materi & Buat Soal", use_container_width=True, type="primary"):
        reset_materi_state()
        st.session_state.page = "upload"
        st.rerun()

# ============================================================
# HALAMAN: UPLOAD MATERI
# ============================================================
def render_upload():
    if st.button("⬅ Kembali ke Menu Utama"):
        st.session_state.page = "home"
        st.rerun()

    st.title("📄 Upload Materi")
    st.info(
        "Sebelum memulai, silahkan upload materi terlebih dahulu (format PDF). "
        "Topik soal akan mengikuti isi materi yang kamu upload, apa pun topiknya.\n\n"
        f"⚠️ Batasan saat ini: maksimal **{MAX_PDF_PAGES} halaman**. "
        "Jika PDF lebih dari itu, upload akan ditolak."
    )

    uploaded_file = st.file_uploader("Upload materi (PDF)", type=["pdf"])

    if uploaded_file is not None:
        with st.spinner("Memeriksa dan membaca materi..."):
            materi_text, num_pages = read_uploaded_pdf(uploaded_file, MAX_PDF_PAGES)

        if materi_text is None:
            st.error(
                f"PDF yang kamu upload memiliki **{num_pages} halaman**. "
                f"Maksimal yang diizinkan saat ini adalah **{MAX_PDF_PAGES} halaman**. "
                "Silahkan upload ulang dengan PDF yang lebih pendek."
            )
        elif not materi_text.strip():
            st.error(
                "Tidak ada teks yang bisa dibaca dari PDF ini "
                "(kemungkinan PDF berupa hasil scan/gambar). Coba upload PDF lain."
            )
        else:
            st.session_state.materi_text = materi_text
            st.session_state.materi_filename = uploaded_file.name
            reset_chat_state()
            st.success(f"Materi '{uploaded_file.name}' berhasil diupload ({num_pages} halaman).")
            st.session_state.page = "chat"
            st.rerun()


# ============================================================
# HALAMAN: CHATBOT
# ============================================================
def render_chat():
    top_left, top_right = st.columns([1, 3])
    with top_left:
        if st.button("⬅ Kembali ke Menu Utama"):
            st.session_state.page = "home"
            st.rerun()
    with top_right:
        st.caption(f"📄 Materi aktif: **{st.session_state.get('materi_filename') or '-'}**")

    st.title("🎓 Chatbot Soal Latihan")

    materi_text = st.session_state.get("materi_text")
    if not materi_text:
        st.warning("Materi belum diupload. Silahkan upload materi terlebih dahulu.")
        if st.button("Ke Halaman Upload"):
            st.session_state.page = "upload"
            st.rerun()
        return

    st.info(
        "Silahkan ajukan pertanyaan atau minta dibuatkan soal berdasarkan "
        "materi yang diberikan. Ketik **'kunci jawaban'** untuk melihat jawabannya."
    )

    # Tampilkan riwayat chat
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_input = st.chat_input("Ketik pesan Anda di sini...")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    normalized = user_input.strip().lower()

    with st.chat_message("assistant"):
        with st.spinner("Sedang memproses..."):

            if any(kw in normalized for kw in SOAL_TRIGGER_KEYWORDS):
                quiz_text, answer_text = generate_quiz(materi_text)
                st.session_state.current_answer_text = answer_text
                bot_reply = (
                    f"{quiz_text}\n\n"
                    "📌 Jika ingin mengetahui jawabannya, silahkan ketik **'kunci jawaban'**."
                )

            elif "kunci" in normalized and "jawaban" in normalized:
                if st.session_state.current_answer_text:
                    bot_reply = st.session_state.current_answer_text
                else:
                    bot_reply = (
                        "Soal belum dibuat. Ketik **'buat soal'** terlebih dahulu untuk "
                        "membuat soal latihan."
                    )

            else:
                bot_reply = grounded_chat(materi_text, st.session_state.messages, user_input)

        st.markdown(bot_reply)

    st.session_state.messages.append({"role": "assistant", "content": bot_reply})


# ============================================================
# MAIN
# ============================================================
def main():
    st.set_page_config(page_title="Schoool Question Generated", page_icon="📚")
    init_state()

    page = st.session_state.page
    if page == "home":
        render_home()
    elif page == "upload":
        render_upload()
    else:
        render_chat()


if __name__ == "__main__":
    main()