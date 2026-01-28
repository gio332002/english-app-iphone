import streamlit as st
import pandas as pd
import random
from gtts import gTTS
import os
import time

# --- CẤU HÌNH ---
FILE_PATH = "data_hoc_tap.xlsx"
SHEET_REVIEW = "Review"
SHEET_UNSURE = "Unsure"

# --- HÀM HỖ TRỢ ---
def load_data(sheet_name, part=None):
    try:
        df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
        if part == 1:
            df = df.iloc[:, [0, 1]]
        elif part == 2:
            df = df.iloc[:, [2, 3]]
        
        df.columns = ['Question', 'Answer']
        df = df.dropna()
        # Chuyển thành list dictionary và shuffle
        data = df.to_dict('records')
        random.shuffle(data)
        return data
    except:
        return []

def get_audio_html(text):
    # Tạo file mp3 tạm thời
    try:
        tts = gTTS(text=str(text), lang='en')
        filename = "temp_audio.mp3"
        tts.save(filename)
        # Đọc file để phát
        audio_file = open(filename, 'rb')
        audio_bytes = audio_file.read()
        return audio_bytes
    except: return None

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="English Master", page_icon="🎓")

st.title("🎓 English Master Mobile")

# --- KHỞI TẠO SESSION STATE (Bộ nhớ phiên làm việc) ---
if 'questions' not in st.session_state:
    st.session_state.questions = []
if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'show_result' not in st.session_state:
    st.session_state.show_result = False
if 'hint_revealed' not in st.session_state:
    st.session_state.hint_revealed = False

# --- SIDEBAR (MENU) ---
with st.sidebar:
    st.header("Cài đặt")
    try:
        xls = pd.ExcelFile(FILE_PATH)
        sheets = [s for s in xls.sheet_names if s not in [SHEET_REVIEW, SHEET_UNSURE]]
    except:
        sheets = []
        st.error("Không tìm thấy file Excel!")

    selected_unit = st.selectbox("Chọn Unit:", sheets)
    selected_part = st.radio("Chọn phần:", [1, 2], format_func=lambda x: f"Phần {x}")
    
    if st.button("BẮT ĐẦU HỌC 🚀"):
        data = load_data(selected_unit, selected_part)
        if data:
            st.session_state.questions = data
            st.session_state.current_idx = 0
            st.session_state.score = 0
            st.session_state.show_result = False
            st.session_state.hint_revealed = False
            st.rerun() # Load lại trang
        else:
            st.warning("Unit này không có dữ liệu!")

# --- MÀN HÌNH HỌC TẬP ---
if len(st.session_state.questions) > 0:
    # Lấy câu hỏi hiện tại
    idx = st.session_state.current_idx
    if idx < len(st.session_state.questions):
        q_data = st.session_state.questions[idx]
        total = len(st.session_state.questions)
        
        # Thanh tiến trình
        st.progress((idx) / total)
        st.caption(f"Câu {idx + 1}/{total}")

        # Hiển thị câu hỏi
        st.info(f"❓: {q_data['Question']}")
        
        # Audio Câu hỏi
        if st.button("🔊 Nghe câu hỏi"):
             audio_bytes = get_audio_html(q_data['Question'])
             if audio_bytes: st.audio(audio_bytes, format='audio/mp3')

        # Gợi ý
        ans = str(q_data['Answer'])
        if st.button("💡 Gợi ý"):
            st.session_state.hint_revealed = True
        
        if st.session_state.hint_revealed:
            # Logic hiển thị gợi ý kiểu _ _ _
            masked = "".join([c if c == " " else "_ " for c in ans])
            st.warning(f"Gợi ý: {masked} (Ký tự đầu: {ans[0]})")

        # Ô nhập liệu
        user_input = st.text_input("Nhập đáp án:", key=f"input_{idx}")

        if st.button("Trả lời"):
            if user_input.strip().lower() == ans.strip().lower():
                st.success("✅ CHÍNH XÁC!")
                st.balloons()
                st.session_state.score += 1
                
                # Audio Đáp án
                audio_ans = get_audio_html(ans)
                if audio_ans: st.audio(audio_ans, format='audio/mp3')
                
                time.sleep(1) # Chờ 1 chút
                st.session_state.current_idx += 1
                st.session_state.hint_revealed = False
                st.rerun()
            else:
                st.error(f"❌ Sai rồi! Đáp án đúng là: {ans}")
                # Audio Đáp án khi sai
                audio_ans = get_audio_html(ans)
                if audio_ans: st.audio(audio_ans, format='audio/mp3')
                
                if st.button("Tiếp tục (Bỏ qua câu này)"):
                    st.session_state.current_idx += 1
                    st.session_state.hint_revealed = False
                    st.rerun()

    else:
        st.success(f"🎉 HOÀN THÀNH! Kết quả: {st.session_state.score}/{len(st.session_state.questions)}")
        if st.button("Học lại"):
            st.session_state.current_idx = 0
            st.session_state.score = 0
            st.rerun()
else:
    st.info("👈 Hãy chọn Unit bên menu trái và nhấn BẮT ĐẦU.")