import streamlit as st
import pandas as pd
import random
from gtts import gTTS
import os
import time
from openpyxl import load_workbook

# --- CẤU HÌNH ---
FILE_PATH = "data_hoc_tap.xlsx"
SHEET_REVIEW = "Review"
SHEET_UNSURE = "Unsure"

st.set_page_config(page_title="English Master", page_icon="🎓", layout="wide")

# --- HÀM HỖ TRỢ AN TOÀN ---
def standardize_dataframe(df, source_name_default="Unknown"):
    if len(df.columns) == 2:
        df.columns = ['Question', 'Answer']
        df['Source'] = source_name_default
    elif len(df.columns) >= 3:
        df = df.iloc[:, 0:3] 
        df.columns = ['Question', 'Answer', 'Source']
    df = df.dropna(subset=['Question', 'Answer'])
    return df

def get_data_count(sheet_name):
    try:
        df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
        return len(df)
    except: return 0

def remove_from_excel(sheet_name, question_text):
    try:
        df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
        df = standardize_dataframe(df)
        initial_len = len(df)
        df = df[df['Question'].astype(str).str.strip() != str(question_text).strip()]
        
        if len(df) < initial_len:
            with pd.ExcelWriter(FILE_PATH, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            return True
        return False
    except Exception as e:
        st.error(f"Lỗi xóa file: {e}")
        return False

def load_data(sheet_name, part=None):
    try:
        if sheet_name in [SHEET_REVIEW, SHEET_UNSURE]:
            df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
            df = standardize_dataframe(df, source_name_default=sheet_name)
        else:
            full_df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
            if part == 1:
                df = full_df.iloc[:, [0, 1]].copy()
                source_label = f"{sheet_name} (Part 1)"
            else:
                df = full_df.iloc[:, [2, 3]].copy()
                source_label = f"{sheet_name} (Part 2)"
            df = standardize_dataframe(df, source_name_default=source_label)

        if df.empty: return []
        data = df.to_dict('records')
        random.shuffle(data)
        return data
    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu: {e}")
        return []

def save_unsure_to_excel(card):
    try:
        new_row = pd.DataFrame([{
            'Question': card['Question'], 'Answer': card['Answer'], 
            'Source': card.get('Source', 'Unknown')
        }])
        try:
            df_old = pd.read_excel(FILE_PATH, sheet_name=SHEET_UNSURE)
            df_old = standardize_dataframe(df_old)
        except:
            df_old = pd.DataFrame(columns=['Question', 'Answer', 'Source'])

        df_combined = pd.concat([df_old, new_row]).drop_duplicates(subset=['Question'], keep='last')
        
        with pd.ExcelWriter(FILE_PATH, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_combined.to_excel(writer, sheet_name=SHEET_UNSURE, index=False)
        return True
    except Exception as e:
        st.error(f"Lỗi lưu file: {e}")
        return False

def get_audio_html(text):
    try:
        filename = f"audio_{random.randint(1000,9999)}.mp3"
        # Dọn dẹp file cũ
        for f in os.listdir():
            if f.endswith(".mp3") and "audio_" in f:
                try: os.remove(f)
                except: pass
        
        tts = gTTS(text=str(text), lang='en')
        tts.save(filename)
        f = open(filename, 'rb')
        audio_bytes = f.read()
        f.close()
        return audio_bytes
    except: return None

# --- STATE ---
if 'questions' not in st.session_state: st.session_state.questions = []
if 'current_idx' not in st.session_state: st.session_state.current_idx = 0
if 'score' not in st.session_state: st.session_state.score = 0
if 'revealed_indices' not in st.session_state: st.session_state.revealed_indices = set()
if 'current_mode' not in st.session_state: st.session_state.current_mode = "learn"
# Biến trạng thái trả lời: None, 'correct', 'wrong'
if 'answer_status' not in st.session_state: st.session_state.answer_status = None 

# --- SIDEBAR ---
st.title("🎓 English Master")

with st.sidebar:
    st.header("📊 Dashboard")
    count_review = get_data_count(SHEET_REVIEW)
    count_unsure = get_data_count(SHEET_UNSURE)
    
    col1, col2 = st.columns(2)
    with col1: st.metric("Cần ôn (Sai)", count_review, delta_color="inverse")
    with col2: st.metric("Chưa chắc", count_unsure, delta_color="off")
    
    st.markdown("---")
    st.header("⚙️ Chọn bài học")
    try:
        xls = pd.ExcelFile(FILE_PATH)
        all_sheets = xls.sheet_names
        unit_sheets = [s for s in all_sheets if s not in [SHEET_REVIEW, SHEET_UNSURE]]
        options = unit_sheets + ["---", "Ôn tập: Câu Sai (Review)", "Ôn tập: Chưa Chắc (Unsure)"]
    except:
        st.error("Chưa có file Excel!")
        options = []

    selected_option = st.selectbox("Danh sách:", options)

    selected_part = None
    target_mode = "learn"
    
    if selected_option == "Ôn tập: Câu Sai (Review)": target_mode = "review"
    elif selected_option == "Ôn tập: Chưa Chắc (Unsure)": target_mode = "unsure"
    elif selected_option != "---":
        st.caption("Cấu trúc Unit:")
        selected_part = st.radio("Chọn phần:", [1, 2], format_func=lambda x: f"Phần {x} (Cột {'A-B' if x==1 else 'C-D'})")

    if st.button("BẮT ĐẦU HỌC 🚀", type="primary"):
        target_sheet = ""
        if target_mode == "review": target_sheet = SHEET_REVIEW
        elif target_mode == "unsure": target_sheet = SHEET_UNSURE
        elif selected_option != "---": target_sheet = selected_option
        
        if target_sheet:
            data = load_data(target_sheet, selected_part)
            if data:
                st.session_state.questions = data
                st.session_state.current_idx = 0
                st.session_state.score = 0
                st.session_state.revealed_indices = set()
                st.session_state.current_mode = target_mode
                st.session_state.answer_status = None # Reset trạng thái
                st.rerun()
            else:
                st.warning("Bài này chưa có dữ liệu!")

# --- MAIN SCREEN ---
if len(st.session_state.questions) > 0:
    idx = st.session_state.current_idx
    
    if idx < len(st.session_state.questions):
        q_data = st.session_state.questions[idx]
        total = len(st.session_state.questions)
        answer_text = str(q_data['Answer']).strip()
        
        # 1. Info Bar
        st.progress((idx) / total)
        st.caption(f"Câu {idx + 1}/{total} | Chế độ: {st.session_state.current_mode.upper()}")

        # 2. Question Area
        st.info(f"❓: {q_data['Question']}")
        
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("🔊 Nghe câu hỏi"):
                audio_bytes = get_audio_html(q_data['Question'])
                if audio_bytes: st.audio(audio_bytes, format='audio/mp3')
        with c3:
            if st.session_state.current_mode != "unsure":
                if st.button("💾 Lưu nghi ngờ"):
                    if save_unsure_to_excel(q_data): st.toast("Đã lưu!", icon="✅")

        # Hint Visual
        st.write("---")
        hint_html = "<div style='line-height: 2.5;'>"
        for i, char in enumerate(answer_text):
            if char == " ": hint_html += "&nbsp;&nbsp;"
            elif i in st.session_state.revealed_indices:
                hint_html += f"<span style='color:#d63031; border:1px solid #fab1a0; padding:2px 8px; margin:1px; background:#ffeaa7; border-radius:4px'><b>{char}</b></span>"
            else:
                hint_html += f"<span style='color:#b2bec3; border:1px solid #dfe6e9; padding:2px 8px; margin:1px; background:#f5f6fa; border-radius:4px'>_</span>"
        hint_html += "</div>"
        st.markdown(hint_html, unsafe_allow_html=True)
        
        if st.button("💡 Mở 1 chữ cái"):
            unrevealed = [i for i, c in enumerate(answer_text) if c != " " and i not in st.session_state.revealed_indices]
            if unrevealed:
                st.session_state.revealed_indices.add(random.choice(unrevealed))
                st.rerun()

        # 3. Answer Form (Chỉ hiện khi chưa trả lời đúng)
        if st.session_state.answer_status != 'correct':
            with st.form(key=f"form_{idx}"):
                user_input = st.text_input("Nhập đáp án:")
                submitted = st.form_submit_button("Trả lời")
            
            if submitted:
                if user_input.strip().lower() == answer_text.lower():
                    st.session_state.answer_status = 'correct'
                    st.session_state.score += 1
                    st.rerun() # Rerun để ẩn form và hiện kết quả
                else:
                    st.session_state.answer_status = 'wrong'
                    st.rerun()

        # --- XỬ LÝ KẾT QUẢ (HIỆN BÊN DƯỚI) ---
        
        # A. KHI TRẢ LỜI ĐÚNG
        if st.session_state.answer_status == 'correct':
            st.success("✅ CHÍNH XÁC!")
            st.balloons()
            
            # Audio Đáp án
            st.write("🔊 Nghe đáp án:")
            audio_ans = get_audio_html(answer_text)
            if audio_ans: st.audio(audio_ans, format='audio/mp3')

            st.markdown("---")
            
            # Nếu là chế độ ÔN TẬP -> Hiện nút Xóa/Giữ
            if st.session_state.current_mode in ["review", "unsure"]:
                st.info("💡 Bạn đã thuộc bài này chưa?")
                c_del, c_next = st.columns(2)
                with c_del:
                    if st.button("🗑️ CÓ, XÓA NGAY", type="primary"):
                        sheet_to_del = SHEET_REVIEW if st.session_state.current_mode == "review" else SHEET_UNSURE
                        if remove_from_excel(sheet_to_del, q_data['Question']):
                            st.toast("Đã xóa!", icon="🗑️")
                        
                        # Reset và qua câu mới
                        st.session_state.current_idx += 1
                        st.session_state.revealed_indices = set()
                        st.session_state.answer_status = None
                        st.rerun()
                
                with c_next:
                    if st.button("➡️ GIỮ LẠI & TIẾP TỤC"):
                        st.session_state.current_idx += 1
                        st.session_state.revealed_indices = set()
                        st.session_state.answer_status = None
                        st.rerun()
            
            # Nếu là chế độ HỌC THƯỜNG -> Hiện nút Tiếp tục
            else:
                if st.button("➡️ Tiếp tục câu sau", type="primary"):
                    st.session_state.current_idx += 1
                    st.session_state.revealed_indices = set()
                    st.session_state.answer_status = None
                    st.rerun()

        # B. KHI TRẢ LỜI SAI
        elif st.session_state.answer_status == 'wrong':
            st.error(f"❌ Sai rồi! Đáp án đúng: {answer_text}")
            
            st.write("🔊 Nghe đáp án:")
            audio_ans = get_audio_html(answer_text)
            if audio_ans: st.audio(audio_ans, format='audio/mp3')
            
            if st.button("➡️ Tiếp tục (Đi câu sau)"):
                # Logic lưu vào Review nếu đang học thường
                if st.session_state.current_mode == "learn":
                    try:
                        new_row = pd.DataFrame([{
                            'Question': q_data['Question'], 'Answer': q_data['Answer'], 
                            'Source': q_data.get('Source', 'Unknown')
                        }])
                        try: df_rev = pd.read_excel(FILE_PATH, sheet_name=SHEET_REVIEW)
                        except: df_rev = pd.DataFrame()
                        df_rev = pd.concat([df_rev, new_row]).drop_duplicates(subset=['Question'], keep='last')
                        with pd.ExcelWriter(FILE_PATH, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                            df_rev.to_excel(writer, sheet_name=SHEET_REVIEW, index=False)
                    except: pass
                
                # Qua câu mới
                st.session_state.current_idx += 1
                st.session_state.revealed_indices = set()
                st.session_state.answer_status = None
                st.rerun()
            
            if st.button("🔄 Thử lại"):
                st.session_state.answer_status = None
                st.rerun()

    else:
        st.success(f"🎉 HOÀN THÀNH! Kết quả: {st.session_state.score}/{len(st.session_state.questions)}")
        if st.button("🔄 Học lại bài này"):
            st.session_state.current_idx = 0
            st.session_state.score = 0
            st.session_state.revealed_indices = set()
            st.session_state.answer_status = None
            random.shuffle(st.session_state.questions)
            st.rerun()

else:
    st.info("👈 Chọn bài học ở Menu bên trái.")
