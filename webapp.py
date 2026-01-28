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

# --- HÀM HỖ TRỢ ---
def standardize_dataframe(df, source_name_default="Unknown"):
    """Đảm bảo DataFrame luôn có 3 cột chuẩn"""
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

def get_unique_sources(sheet_name):
    """Lấy danh sách các Unit đang có trong sheet Review/Unsure"""
    try:
        df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
        df = standardize_dataframe(df, sheet_name)
        if 'Source' in df.columns:
            sources = df['Source'].unique().tolist()
            return sorted([str(s) for s in sources])
        return []
    except: return []

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

def load_data(mode, sheet_name_or_source, part=None):
    """
    mode: 'learn', 'review', 'unsure'
    sheet_name_or_source: Tên Unit (nếu learn) hoặc Tên Source cần lọc (nếu review)
    """
    try:
        # 1. CHẾ ĐỘ ÔN TẬP
        if mode in ['review', 'unsure']:
            target_sheet = SHEET_REVIEW if mode == 'review' else SHEET_UNSURE
            df = pd.read_excel(FILE_PATH, sheet_name=target_sheet)
            df = standardize_dataframe(df, source_name_default=target_sheet)
            
            # Lọc theo Unit cụ thể (Source)
            if sheet_name_or_source != "Tất cả":
                df = df[df['Source'] == sheet_name_or_source]
        
        # 2. CHẾ ĐỘ HỌC MỚI
        else:
            full_df = pd.read_excel(FILE_PATH, sheet_name=sheet_name_or_source)
            if part == 1:
                df = full_df.iloc[:, [0, 1]].copy()
                source_label = f"{sheet_name_or_source} (Part 1)"
            else:
                df = full_df.iloc[:, [2, 3]].copy()
                source_label = f"{sheet_name_or_source} (Part 2)"
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
        return False

def get_audio_html(text):
    try:
        filename = f"audio_{random.randint(1000,9999)}.mp3"
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
if 'answer_status' not in st.session_state: st.session_state.answer_status = None 

# --- SIDEBAR (MENU CẢI TIẾN) ---
st.title("🎓 English Master")

with st.sidebar:
    st.header("📊 Dashboard")
    c_rev = get_data_count(SHEET_REVIEW)
    c_uns = get_data_count(SHEET_UNSURE)
    col1, col2 = st.columns(2)
    with col1: st.metric("Cần ôn", c_rev, delta_color="inverse")
    with col2: st.metric("Chưa chắc", c_uns, delta_color="off")
    st.markdown("---")

    st.header("⚙️ Cài đặt học")
    
    # 1. CHỌN CHẾ ĐỘ TRƯỚC
    study_mode = st.radio("Chế độ:", ["Học bài mới", "Ôn tập câu Sai", "Ôn tập Chưa chắc"])
    
    selected_unit_or_source = None
    selected_part = None
    
    # 2. HIỂN THỊ MENU CON TÙY THEO CHẾ ĐỘ
    try:
        if study_mode == "Học bài mới":
            xls = pd.ExcelFile(FILE_PATH)
            # Lấy list Unit
            unit_sheets = [s for s in xls.sheet_names if s not in [SHEET_REVIEW, SHEET_UNSURE]]
            selected_unit_or_source = st.selectbox("Chọn Unit:", unit_sheets)
            
            if selected_unit_or_source:
                selected_part = st.radio("Chọn phần:", [1, 2], format_func=lambda x: f"Phần {x} (Cột {'A-B' if x==1 else 'C-D'})")
                
        elif study_mode == "Ôn tập câu Sai":
            # Lấy list nguồn trong Review
            sources = get_unique_sources(SHEET_REVIEW)
            if not sources:
                st.warning("Chưa có câu sai nào!")
            else:
                sources = ["Tất cả"] + sources
                selected_unit_or_source = st.selectbox("Chọn nguồn ôn:", sources)
                
        elif study_mode == "Ôn tập Chưa chắc":
            # Lấy list nguồn trong Unsure
            sources = get_unique_sources(SHEET_UNSURE)
            if not sources:
                st.warning("Chưa có câu chưa chắc nào!")
            else:
                sources = ["Tất cả"] + sources
                selected_unit_or_source = st.selectbox("Chọn nguồn ôn:", sources)

    except Exception as e:
        st.error(f"Lỗi file Excel: {e}")

    # NÚT BẮT ĐẦU
    if st.button("BẮT ĐẦU HỌC 🚀", type="primary"):
        internal_mode = "learn"
        if study_mode == "Ôn tập câu Sai": internal_mode = "review"
        elif study_mode == "Ôn tập Chưa chắc": internal_mode = "unsure"
        
        if selected_unit_or_source:
            data = load_data(internal_mode, selected_unit_or_source, selected_part)
            if data:
                st.session_state.questions = data
                st.session_state.current_idx = 0
                st.session_state.score = 0
                st.session_state.revealed_indices = set()
                st.session_state.current_mode = internal_mode
                st.session_state.answer_status = None
                st.rerun()
            else:
                st.warning("Không có dữ liệu!")

# --- MAIN SCREEN ---
if len(st.session_state.questions) > 0:
    idx = st.session_state.current_idx
    
    if idx < len(st.session_state.questions):
        q_data = st.session_state.questions[idx]
        total = len(st.session_state.questions)
        answer_text = str(q_data['Answer']).strip()
        
        # Thanh tiến trình + Info
        st.progress((idx) / total)
        st.caption(f"Câu {idx + 1}/{total} | {st.session_state.current_mode.upper()} | Nguồn: {q_data.get('Source', 'Unknown')}")

        # Câu hỏi
        st.info(f"❓: {q_data['Question']}")
        
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("🔊 Nghe câu hỏi"):
                audio_bytes = get_audio_html(q_data['Question'])
                if audio_bytes: st.audio(audio_bytes, format='audio/mp3')
        with c3:
            # Nút Lưu thủ công (Ẩn nếu đang ở chế độ Unsure để tránh lưu trùng)
            if st.session_state.current_mode != "unsure":
                if st.button("💾 Lưu nghi ngờ"):
                    if save_unsure_to_excel(q_data): st.toast("Đã lưu!", icon="✅")

        # --- VISUAL HINT ---
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
        
        # --- NÚT GỢI Ý & AUTO SAVE ---
        if st.button("💡 Mở 1 chữ cái"):
            unrevealed = [i for i, c in enumerate(answer_text) if c != " " and i not in st.session_state.revealed_indices]
            if unrevealed:
                # 1. Mở chữ
                st.session_state.revealed_indices.add(random.choice(unrevealed))
                
                # 2. TỰ ĐỘNG LƯU UNSURE (Logic bạn yêu cầu)
                # Chỉ lưu nếu không phải đang học trong chính mục Unsure
                if st.session_state.current_mode != "unsure":
                    if save_unsure_to_excel(q_data):
                        st.toast("Dùng gợi ý -> Đã tự động lưu vào 'Chưa chắc'", icon="💾")
                
                st.rerun()

        # FORM TRẢ LỜI
        if st.session_state.answer_status != 'correct':
            with st.form(key=f"form_{idx}"):
                user_input = st.text_input("Nhập đáp án:")
                submitted = st.form_submit_button("Trả lời")
            
            if submitted:
                if user_input.strip().lower() == answer_text.lower():
                    st.session_state.answer_status = 'correct'
                    st.session_state.score += 1
                    st.rerun()
                else:
                    st.session_state.answer_status = 'wrong'
                    st.rerun()

        # --- XỬ LÝ KẾT QUẢ ---
        if st.session_state.answer_status == 'correct':
            st.success("✅ CHÍNH XÁC!")
            st.balloons()
            st.write("🔊 Nghe đáp án:")
            audio_ans = get_audio_html(answer_text)
            if audio_ans: st.audio(audio_ans, format='audio/mp3')

            st.markdown("---")
            
            # Logic XÓA nếu đang Ôn tập
            if st.session_state.current_mode in ["review", "unsure"]:
                st.info("💡 Bạn đã thuộc bài này chưa?")
                c_del, c_next = st.columns(2)
                with c_del:
                    if st.button("🗑️ CÓ, XÓA LUÔN", type="primary"):
                        sheet_to_del = SHEET_REVIEW if st.session_state.current_mode == "review" else SHEET_UNSURE
                        if remove_from_excel(sheet_to_del, q_data['Question']):
                            st.toast("Đã xóa khỏi danh sách!", icon="🗑️")
                        
                        st.session_state.current_idx += 1
                        st.session_state.revealed_indices = set()
                        st.session_state.answer_status = None
                        st.rerun()
                with c_next:
                    if st.button("➡️ GIỮ LẠI ÔN TIẾP"):
                        st.session_state.current_idx += 1
                        st.session_state.revealed_indices = set()
                        st.session_state.answer_status = None
                        st.rerun()
            else:
                if st.button("➡️ Tiếp tục câu sau", type="primary"):
                    st.session_state.current_idx += 1
                    st.session_state.revealed_indices = set()
                    st.session_state.answer_status = None
                    st.rerun()

        elif st.session_state.answer_status == 'wrong':
            st.error(f"❌ Sai rồi! Đáp án đúng: {answer_text}")
            audio_ans = get_audio_html(answer_text)
            if audio_ans: st.audio(audio_ans, format='audio/mp3')
            
            if st.button("➡️ Tiếp tục (Đi câu sau)"):
                # Lưu vào Review nếu đang học mới
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
    st.info("👈 Chọn Chế độ và Bài học ở Menu bên trái.")
