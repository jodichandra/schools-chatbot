"""
School Question Generated For 3 SD
Final Project - Chatbot Pembuat Soal Latihan Berbasis Materi PDF (OpenAI API)

Cara pakai singkat:
1. Taruh file PDF materi di folder materi/ (lihat MATERI_PDF_PATH di bawah)
2. Isi MATERI_LINK dengan link akses materi (misal Google Drive)
3. Isi OPENAI_API_KEY di .streamlit/secrets.toml
4. Jalankan: streamlit run app.py
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

# Path file PDF materi Muatan Lokal (taruh file kamu di sini)
MATERI_PDF_PATH = os.path.join("materi", "budaya_minangkabau.pdf")

# Link yang muncul di tombol "akses materi" pada halaman chatbot
MATERI_LINK = "https://drive.google.com/file/d/1vEwpOnOTbYez3_VW8mWlN7q5hB6j0vot/view?usp=sharing"  # TODO: ganti dengan link materi asli

TEMPLATE_GREETING = (
    "Hallo saya chatbot khusus untuk membuat soal berdasarkan pelajaran yang "
    "dipilih..silahkan ketik ya agar saya bisa membuat soal untuk anda?"
)

YA_VARIANTS = {"ya", "iya", "y", "ok", "oke", "siap", "boleh", "mau", "yes"}


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
# UTIL: BACA PDF MATERI
# ============================================================
@st.cache_data(show_spinner=False)
def load_materi_text(pdf_path: str) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


# ============================================================
# GENERATE SOAL (dipisah dari kunci jawaban)
# ============================================================
def generate_quiz(materi_text: str, n_soal: int = 5):
    client = get_openai_client()

    system_prompt = f"""Kamu adalah guru SD kelas 3 yang membuat soal latihan.
Gunakan HANYA informasi dari MATERI di bawah ini, jangan menambah informasi dari luar materi.
Bahasa harus sederhana, sesuai untuk anak kelas 3 SD.

Buat {n_soal} soal pilihan ganda (A-D) berdasarkan MATERI berikut.

Balas HANYA dalam format JSON persis seperti ini, tanpa teks tambahan apa pun:
{{
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
        # fallback kalau model tidak mengembalikan JSON valid
        return raw, "Kunci jawaban tidak tersedia karena format soal tidak sesuai. Coba ketik 'ya' lagi."

    soal_list = data.get("soal", [])
    kunci_list = data.get("kunci_jawaban", [])

    quiz_lines = ["📝 **Soal Latihan - BAM**", ""]
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
# CHAT UMUM (tetap dibatasi hanya pada materi PDF)
# ============================================================
def grounded_chat(materi_text: str, history: list, user_input: str) -> str:
    client = get_openai_client()

    system_prompt = f"""Kamu adalah chatbot ramah untuk siswa kelas 3 SD dengan topik
'Budaya Adat Minangkabau'.

ATURAN PENTING:
1. Kamu HANYA boleh menjawab berdasarkan MATERI di bawah ini.
2. Jika pertanyaan user tidak berkaitan dengan materi ini, tolak dengan sopan
   dan arahkan user untuk mengetik 'ya' agar dibuatkan soal latihan.
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
    st.session_state.setdefault("page", "home")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("stage", "initial")  # initial -> awaiting_ya -> quiz_shown
    st.session_state.setdefault("current_answer_text", None)


def reset_chat_state():
    st.session_state.messages = []
    st.session_state.stage = "initial"
    st.session_state.current_answer_text = None


# ============================================================
# HALAMAN: HOME
# ============================================================
def render_home():
    st.title("📚 Schoool Question Generated")
    st.write("Selamat datang! Pilih mata pelajaran untuk membuat soal latihan.")

    st.subheader("Muatan Lokal")
    if st.button("🏯 Budaya Adat Minangkabau", use_container_width=True, type="primary"):
        reset_chat_state()
        st.session_state.page = "chat"
        st.rerun()

    st.divider()

    st.subheader("Daftar Pelajaran")
    cols = st.columns(3)
    coming_soon_subjects = ["Bahasa Inggris", "Bahasa Indonesia", "Matematika"]
    for col, subject in zip(cols, coming_soon_subjects):
        with col:
            st.button(f"🔒 {subject}", disabled=True, use_container_width=True)
            st.caption("Coming Soon")


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
        st.link_button("🔗 Klik di sini untuk akses materi", MATERI_LINK)

    st.caption("Silahkan klik link di atas untuk akses materi.")
    st.title("🎓 Chatbot Soal - BAM")

    # Load materi PDF sekali saja (di-cache)
    if not os.path.exists(MATERI_PDF_PATH):
        st.error(
            f"File materi tidak ditemukan di `{MATERI_PDF_PATH}`. "
            "Silahkan tambahkan file PDF materi terlebih dahulu di folder `materi/`."
        )
        st.stop()

    materi_text = load_materi_text(MATERI_PDF_PATH)

    # Tampilkan riwayat chat
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_input = st.chat_input("Ketik pesan Anda di sini...")
    if not user_input:
        return

    # Tampilkan pesan user
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    normalized = user_input.strip().lower()

    with st.chat_message("assistant"):
        with st.spinner("Sedang memproses..."):

            if st.session_state.stage == "initial":
                bot_reply = TEMPLATE_GREETING
                st.session_state.stage = "awaiting_ya"

            elif st.session_state.stage == "awaiting_ya" and normalized in YA_VARIANTS:
                quiz_text, answer_text = generate_quiz(materi_text)
                st.session_state.current_answer_text = answer_text
                bot_reply = (
                    f"{quiz_text}\n\n"
                    "📌 Jika ingin mengetahui jawabannya, silahkan ketik **'kunci jawaban'**."
                )
                st.session_state.stage = "quiz_shown"

            elif "kunci" in normalized and "jawaban" in normalized:
                if st.session_state.current_answer_text:
                    bot_reply = st.session_state.current_answer_text
                else:
                    bot_reply = (
                        "Soal belum dibuat. Ketik **'ya'** terlebih dahulu untuk "
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

    if st.session_state.page == "home":
        render_home()
    else:
        render_chat()


if __name__ == "__main__":
    main()
