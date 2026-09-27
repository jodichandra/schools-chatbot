"""
School Question Generated For 3 SD
Final Project - Chatbot Pembuat Soal Latihan Berbasis Materi PDF Upload User (OpenAI API)
"""

import os
import re
import json

import streamlit as st
import pdfplumber
from openai import OpenAI


# ============================================================
# KONFIGURASI
# ============================================================
MODEL_NAME = "gpt-4o-mini"
MAX_PDF_PAGES = 5

SOAL_TRIGGER_PATTERNS = [
    r"\bbuat(?:kan)?\s+soal\b",
    r"\bbikin(?:kan)?\s+soal\b",
    r"\bsoal\s+latihan\b",
    r"\bkuis\b",
    r"\bquiz\b",
    r"\bgenerate\s+soal\b",
]

KUNCI_JAWABAN_PATTERN = r"\bkunci\s+jawaban\b"


def is_soal_trigger(normalized_text: str) -> bool:
    return any(re.search(pattern, normalized_text) for pattern in SOAL_TRIGGER_PATTERNS)


def is_kunci_jawaban_request(normalized_text: str) -> bool:
    return re.search(KUNCI_JAWABAN_PATTERN, normalized_text) is not None


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
            "`.streamlit/secrets.toml` atau sebagai environment variable."
        )
        st.stop()

    return OpenAI(api_key=api_key)


# ============================================================
# UTIL: BACA PDF
# ============================================================
def read_uploaded_pdf(uploaded_file, max_pages: int = MAX_PDF_PAGES):
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
# GENERATE SOAL
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
        return {
            "quiz_text": raw,
            "answer_text": "Kunci jawaban tidak tersedia karena format soal tidak sesuai.",
            "soal_list": [],
            "kunci_list": [],
            "topik": "",
        }

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

    return {
        "quiz_text": quiz_text,
        "answer_text": answer_text,
        "soal_list": soal_list,
        "kunci_list": kunci_list,
        "topik": topik,
    }


# ============================================================
# CHAT UMUM
# ============================================================
OUT_OF_CONTEXT_MESSAGE = (
    "Maaf, pertanyaan itu tidak sesuai dengan materi yang diupload. "
    "Saya hanya bisa menjawab berdasarkan materi ini. 😊"
)

CODE_REQUEST_MESSAGE = (
    "Maaf, saya hanya bisa menjelaskan sesuai isi materi. "
    "Saya tidak bisa membuatkan kode program, aplikasi, atau halaman web apa pun."
)


def grounded_chat(materi_text: str, history: list, user_input: str) -> str:
    client = get_openai_client()

    system_prompt = f"""Kamu bertugas mengklasifikasikan dan menjawab pertanyaan siswa kelas 3 SD.

Tugas kamu:
1. Tentukan apakah PERTANYAAN USER relevan dengan MATERI di bawah ini.
2. Tentukan apakah PERTANYAAN USER adalah permintaan untuk MEMBUAT, MENULIS, atau
   MEMPERBAIKI kode program, aplikasi, script, atau halaman web apa pun.
3. Jika relevan DAN BUKAN permintaan kode: isi field "jawaban" dengan jawaban
   untuk siswa, HANYA berdasarkan isi MATERI, bahasa sederhana untuk anak kelas 3 SD.
4. Jika tidak relevan ATAU merupakan permintaan kode: kosongkan field "jawaban".

Balas HANYA dalam format JSON berikut:
{{
  "relevan": true atau false,
  "permintaan_kode": true atau false,
  "jawaban": ""
}}

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
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "Maaf, terjadi kendala saat memproses jawaban. Coba tanyakan lagi."

    if data.get("permintaan_kode"):
        return CODE_REQUEST_MESSAGE

    if not data.get("relevan"):
        return OUT_OF_CONTEXT_MESSAGE

    jawaban = (data.get("jawaban") or "").strip()
    return jawaban if jawaban else OUT_OF_CONTEXT_MESSAGE


# ============================================================
# FORM KUIS INTERAKTIF
# ============================================================
def render_quiz_form():
    quiz_data = st.session_state.get("quiz_data")
    if not quiz_data or not quiz_data.get("soal_list"):
        return

    soal_list = quiz_data["soal_list"]
    kunci_list = quiz_data["kunci_list"]
    version = st.session_state.get("quiz_version", 0)

    st.markdown("#### ✏️ Jawab Soal di Bawah Ini")

    with st.form(key=f"quiz_form_{version}"):
        jawaban_user = {}
        for s in soal_list:
            nomor = s.get("nomor")
            pertanyaan = s.get("pertanyaan")
            pilihan = sorted(s.get("pilihan", {}).items(), key=lambda pair: pair[0])
            option_labels = [f"{opt}. {text}" for opt, text in pilihan]

            pilihan_terpilih = st.radio(
                f"{nomor}. {pertanyaan}",
                options=option_labels,
                index=None,
                key=f"quiz_radio_{version}_{nomor}",
            )
            jawaban_user[nomor] = pilihan_terpilih.split(".")[0].strip() if pilihan_terpilih else None

        submitted = st.form_submit_button("📊 Lihat Hasil", use_container_width=True)

    if submitted:
        kunci_map = {k.get("nomor"): k.get("jawaban") for k in kunci_list}
        total_soal = len(kunci_map)
        jumlah_benar = 0
        detail_lines = []

        for nomor in sorted(kunci_map.keys()):
            jawaban_benar = kunci_map[nomor]
            jawaban_dipilih = jawaban_user.get(nomor)
            benar = jawaban_dipilih == jawaban_benar
            if benar:
                jumlah_benar += 1
            status = "✅ Benar" if benar else f"❌ Salah (jawaban benar: **{jawaban_benar}**)"
            detail_lines.append(f"- Soal {nomor}: kamu jawab **{jawaban_dipilih or '(belum dijawab)'}** — {status}")

        skor = round((jumlah_benar / total_soal) * 100) if total_soal else 0
        hasil_text = (
            f"🎯 **Hasil Kuis: {skor} / 100** ({jumlah_benar} dari {total_soal} soal benar)\n\n"
            + "\n".join(detail_lines)
        )

        st.session_state.quiz_result = hasil_text

    if st.session_state.get("quiz_result"):
        st.markdown("---")
        st.markdown(st.session_state.quiz_result)
        st.markdown("")
        if st.button("🗑️ Clear Soal", use_container_width=True, key="clear_soal_btn"):
            st.session_state.quiz_data = None
            st.session_state.quiz_result = None
            st.session_state.current_answer_text = None
            st.session_state.quiz_version += 1
            st.rerun()


# ============================================================
# STATE HELPERS
# ============================================================
def init_state():
    st.session_state.setdefault("page", "home")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("current_answer_text", None)
    st.session_state.setdefault("materi_text", None)
    st.session_state.setdefault("materi_filename", None)
    st.session_state.setdefault("quiz_data", None)
    st.session_state.setdefault("quiz_result", None)
    st.session_state.setdefault("quiz_version", 0)


def reset_chat_state():
    st.session_state.messages = []
    st.session_state.current_answer_text = None
    st.session_state.quiz_data = None
    st.session_state.quiz_result = None
    st.session_state.quiz_version += 1


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

    st.title("Upload Materi PDF")
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
# CSS: override max-width block-container sesuai mode
# ============================================================
CSS_CENTERED = """
<style>
/* Chat normal: block-container sempit di tengah (seperti layout centered) */
.main .block-container,
[data-testid="stAppViewBlockContainer"] {
    max-width: 780px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
</style>
"""

CSS_WIDE = """
<style>
/* Saat ada soal: block-container jadi full width */
.main .block-container,
[data-testid="stAppViewBlockContainer"] {
    max-width: 100% !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
</style>
"""


# ============================================================
# HALAMAN: CHATBOT
# ============================================================
def render_chat():
    materi_text = st.session_state.get("materi_text")

    quiz_data = st.session_state.get("quiz_data")
    has_quiz = bool(quiz_data and quiz_data.get("soal_list"))

    # Inject CSS sesuai mode: centered (default) atau wide (saat ada soal)
    if has_quiz:
        st.markdown(CSS_WIDE, unsafe_allow_html=True)
    else:
        st.markdown(CSS_CENTERED, unsafe_allow_html=True)

    # ---------- HEADER ----------
    top_left, top_right = st.columns([1, 3])
    with top_left:
        if st.button("⬅ Kembali ke Menu Utama"):
            st.session_state.page = "home"
            st.rerun()
    with top_right:
        st.caption(f"📄 Materi aktif: **{st.session_state.get('materi_filename') or '-'}**")

    st.markdown("### 🎓 Chatbot Soal Latihan")

    if not materi_text:
        st.warning("Materi belum diupload. Silahkan upload materi terlebih dahulu.")
        if st.button("Ke Halaman Upload"):
            st.session_state.page = "upload"
            st.rerun()
        return

    # ---------- LAYOUT ----------
    if has_quiz:
        col_chat, col_soal = st.columns([1, 1], gap="medium")
    else:
        col_chat = st.container()
        col_soal = None

    # ------------------------------------------------------------------
    # KOLOM KIRI: CHAT
    # ------------------------------------------------------------------
    with col_chat:
        st.markdown("#### 💬 Chat")
        st.caption(
            "Ajukan pertanyaan berdasarkan materi, atau ketik **'buat soal'** untuk "
            "dibuatkan soal latihan."
        )

        # Container scroll internal untuk bubble chat.
        # Hanya bubble di dalam container ini yang scroll — halaman tidak ikut scroll.
        chat_box = st.container(height=520, border=True)
        with chat_box:
            if not st.session_state.messages:
                st.caption("_Belum ada pesan. Mulai dengan mengetik pertanyaan di bawah._")
            for m in st.session_state.messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

        # Chat input di luar container => ada di bawah kolom chat
        user_input = st.chat_input("Ketik pesan Anda di sini...")

        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            normalized = user_input.strip().lower()

            with st.spinner("Sedang memproses..."):
                if is_soal_trigger(normalized):
                    quiz_data = generate_quiz(materi_text)
                    st.session_state.quiz_data = quiz_data
                    st.session_state.current_answer_text = quiz_data["answer_text"]
                    st.session_state.quiz_result = None
                    st.session_state.quiz_version += 1
                    topik = quiz_data.get("topik") or ""
                    judul = f" - {topik}" if topik else ""
                    bot_reply = (
                        f"✅ Soal latihan{judul} sudah dibuat! Silahkan jawab lewat panel "
                        "**Soal** di sebelah kanan, lalu klik **'Lihat Hasil'** untuk melihat "
                        "nilai kamu. Atau ketik **'kunci jawaban'** untuk melihat kunci jawabannya."
                    )

                elif is_kunci_jawaban_request(normalized):
                    if st.session_state.current_answer_text:
                        bot_reply = st.session_state.current_answer_text
                    else:
                        bot_reply = (
                            "Soal belum dibuat. Ketik **'buat soal'** terlebih dahulu untuk "
                            "membuat soal latihan."
                        )

                else:
                    bot_reply = grounded_chat(materi_text, st.session_state.messages, user_input)

            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            st.rerun()

    # ------------------------------------------------------------------
    # KOLOM KANAN: SOAL
    # ------------------------------------------------------------------
    if col_soal is not None:
        with col_soal:
            st.markdown("#### 📝 Soal")

            soal_box = st.container(height=520, border=True)
            with soal_box:
                render_quiz_form()


# ============================================================
# MAIN
# ============================================================
def main():
    # Set "centered" sebagai default.
    # CSS akan melebarkan block-container saat ada soal.
    st.set_page_config(
        page_title="Schoool Question Generated",
        page_icon="📚",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
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