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

st.set_page_config(page_title="English Master", page_icon="🎓", layout="centered")

# --- HÀM HỖ TRỢ XỬ LÝ DỮ LIỆU AN TOÀN ---
def standardize_dataframe(df, source_name_default="Unknown"):
    """
    Hàm này đảm bảo mọi DF đều có đủ 3 cột: Question, Answer, Source.
    Tránh lỗi 'Length mismatch' tuyệt đối.
    """
    # Nếu chỉ có 2 cột (ví dụ đọc từ Unit), thêm cột Source
    if len(df.columns) == 2:
        df.columns = ['Question', 'Answer']
        df['Source'] = source_name_default
    # Nếu có 3 cột trở lên (ví dụ đọc từ Review/Unsure)
    elif len(df.columns) >= 3:
        # Chỉ lấy 3 cột đầu
        df = df.iloc[:, 0:3] 
        df.columns = ['Question', 'Answer', 'Source']
    
    # Xóa dòng trống
    df = df.dropna(subset=['Question', 'Answer'])
    return df

def load_data(sheet_name, part=None):
    try:
        # 1. Chế độ Ôn tập (Đọc sheet Review hoặc Unsure)
        if sheet_name in [SHEET_REVIEW, SHEET_UNSURE]:
            df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
            # Chuẩn hóa ngay lập tức
            df = standardize_dataframe(df, source_name_default=sheet_name)

        # 2. Chế độ Học Unit (Dựa trên ảnh Excel bạn gửi)
        else:
            full_df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
            
            # Cắt cột dựa trên lựa chọn Part
            if part == 1:
                # Lấy cột A và B (index 0, 1)
                df = full_df.iloc[:, [0, 1]].copy()
                source_label = f"{sheet_name} (Part 1)"
            else:
                # Lấy cột C và D (index 2, 3)
                df = full_df.iloc[:, [2, 3]].copy()
                source_label = f"{sheet_name} (Part 2)"
            
            # Chuẩn hóa
            df = standardize_dataframe(df, source_name_default=source_label)

        if df.empty: return []
        
        # Chuyển thành list và xáo trộn
        data = df.to_dict('records')
        random.shuffle(data)
        return data
        
    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu: {e}")
        return []

def save_unsure_to_excel(card):
    """Lưu câu chưa chắc chắn vào Excel an toàn"""
    try:
        # Tạo dòng dữ liệu mới chuẩn 3 cột
        new_row = pd.DataFrame([{
            'Question': card['Question'], 
            'Answer': card['Answer'], 
            'Source': card.get('Source', 'Unknown')
        }])

        # Đọc dữ liệu cũ lên
        try:
            df_old = pd.read_excel(FILE_PATH, sheet_name=SHEET_UNSURE)
            df_old = standardize_dataframe(df_old)
        except:
            # Nếu chưa có sheet Unsure thì tạo mới
            df_old = pd.DataFrame(columns=['Question', 'Answer', 'Source'])

        # Gộp và xóa trùng lặp
        df_combined = pd.concat([df_old, new_row])
        df_combined = df_combined.drop_duplicates(subset=['Question'], keep='last')
        
        # Ghi đè lại toàn bộ sheet Unsure (An toàn nhất)
        with pd.ExcelWriter(FILE_PATH, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_combined.to_excel(writer, sheet_name=SHEET_UNSURE, index=False)
            
        return True
    except Exception as e:
        st.error(f"Lỗi lưu file (Hãy đóng file Excel trên máy tính): {e}")
        return False

def get_audio_html(text):
    """Tạo file audio tạm để phát trên web"""
    try:
        # Tạo tên file ngẫu nhiên để tránh trình duyệt cache file cũ
        filename = f"audio_{random.randint(1000,9999)}.mp3"
        # Xóa các file mp3 cũ rác
        for f in os.listdir():
            if f.endswith(".mp3") and "audio_" in f:
                try: os.remove(f)
                except: pass
                
        tts = gTTS(text=str(text), lang='en')
        tts.save(filename)
        
        audio_file = open(filename, 'rb')
        audio_bytes = audio_file.read()
        audio_file.close()
        return audio_bytes
    except: return None

# --- KHỞI TẠO TRẠNG THÁI (SESSION STATE) ---
if 'questions' not in st.session_state: st.session_state.questions = []
if 'current_idx' not in st.session_state: st.session_state.current_idx = 0
if 'score' not in st.session_state: st.session_state.score = 0
if 'revealed_indices' not in st.session_state: st.session_state.revealed_indices = set()
if 'audio_key' not in st.session_state: st.session_state.audio_key = 0 # Hack để reload audio player

# --- SIDEBAR (MENU) ---
st.title("🎓 English Master Web")

with st.sidebar:
    st.header("⚙️ Cài đặt")
    try:
        xls = pd.ExcelFile(FILE_PATH)
        all_sheets = xls.sheet_names
        # Lọc ra Unit học (loại bỏ sheet hệ thống)
        unit_sheets = [s for s in all_sheets if s not in [SHEET_REVIEW, SHEET_UNSURE]]
        # Tạo danh sách lựa chọn gồm: Unit học + Các chế độ ôn tập
        options = unit_sheets + ["---", "Ôn tập: Câu Sai (Review)", "Ôn tập: Chưa Chắc (Unsure)"]
    except:
        st.error("Không tìm thấy file Excel!")
        options = []

    selected_option = st.selectbox("Chọn bài học:", options)

    # Logic hiển thị chọn Phần 1 / Phần 2
    selected_part = None
    is_review_mode = False
    
    if selected_option in ["Ôn tập: Câu Sai (Review)", "Ôn tập: Chưa Chắc (Unsure)"]:
        is_review_mode = True
    elif selected_option != "---":
        # Nếu là Unit thường, cho chọn Part
        st.write("Cấu trúc file (Theo ảnh):")
        st.caption("- Phần 1: Cột A & B")
        st.caption("- Phần 2: Cột C & D")
        selected_part = st.radio("Chọn phần:", [1, 2], format_func=lambda x: f"Phần {x}")

    # Nút Bắt đầu
    if st.button("BẮT ĐẦU HỌC 🚀", type="primary"):
        target_sheet = ""
        if selected_option == "Ôn tập: Câu Sai (Review)": target_sheet = SHEET_REVIEW
        elif selected_option == "Ôn tập: Chưa Chắc (Unsure)": target_sheet = SHEET_UNSURE
        elif selected_option != "---": target_sheet = selected_option
        
        if target_sheet:
            data = load_data(target_sheet, selected_part)
            if data:
                st.session_state.questions = data
                st.session_state.current_idx = 0
                st.session_state.score = 0
                st.session_state.revealed_indices = set()
                st.rerun()
            else:
                st.warning("Không có dữ liệu trong bài này!")

# --- MÀN HÌNH CHÍNH ---
if len(st.session_state.questions) > 0:
    idx = st.session_state.current_idx
    
    if idx < len(st.session_state.questions):
        q_data = st.session_state.questions[idx]
        total = len(st.session_state.questions)
        answer_text = str(q_data['Answer']).strip()
        
        # 1. Thanh tiến trình
        st.progress((idx) / total)
        st.caption(f"Câu {idx + 1}/{total} | Nguồn: {q_data.get('Source', 'Unknown')}")

        # 2. Hiển thị câu hỏi
        st.info(f"❓: {q_data['Question']}")
        
        # 3. Audio Câu hỏi
        if st.button("🔊 Nghe câu hỏi"):
            audio_bytes = get_audio_html(q_data['Question'])
            if audio_bytes: 
                # Dùng key ngẫu nhiên để ép player render lại
                st.audio(audio_bytes, format='audio/mp3')

        # 4. Gợi ý thông minh (Lật ô chữ)
        st.write("---")
        st.write("💡 Gợi ý:")
        
        # Render các ô chữ
        hint_html = "<div style='line-height: 2.5;'>"
        for i, char in enumerate(answer_text):
            if char == " ":
                hint_html += "&nbsp;&nbsp;&nbsp;"
            elif i in st.session_state.revealed_indices:
                hint_html += f"<span style='color:#d63031; font-weight:bold; border:1px solid #fab1a0; padding:5px 10px; margin:2px; background:#ffeaa7; border-radius:4px'>{char}</span>"
            else:
                hint_html += f"<span style='color:#b2bec3; border:1px solid #b2bec3; padding:5px 10px; margin:2px; background:#f5f6fa; border-radius:4px'>_</span>"
        hint_html += "</div>"
        st.markdown(hint_html, unsafe_allow_html=True)

        col_hint, col_save = st.columns(2)
        with col_hint:
            if st.button("Mở 1 chữ cái"):
                unrevealed = [i for i, c in enumerate(answer_text) if c != " " and i not in st.session_state.revealed_indices]
                if unrevealed:
                    st.session_state.revealed_indices.add(random.choice(unrevealed))
                    st.rerun()
        
        with col_save:
            if st.button("💾 Lưu 'Chưa chắc'"):
                if save_unsure_to_excel(q_data):
                    st.toast("Đã lưu vào danh sách Unsure!", icon="✅")

        # 5. Form trả lời
        with st.form(key=f"form_{idx}"):
            user_input = st.text_input("Nhập đáp án của bạn:")
            submitted = st.form_submit_button("Kiểm tra")
        
        if submitted:
            if user_input.strip().lower() == answer_text.lower():
                st.success("✅ CHÍNH XÁC!")
                st.balloons()
                st.session_state.score += 1
                
                # Audio Đáp án
                audio_ans = get_audio_html(answer_text)
                if audio_ans: st.audio(audio_ans, format='audio/mp3')
                
                time.sleep(1.5)
                st.session_state.current_idx += 1
                st.session_state.revealed_indices = set()
                st.rerun()
            else:
                st.error(f"❌ Sai rồi! Đáp án đúng: {answer_text}")
                audio_ans = get_audio_html(answer_text)
                if audio_ans: st.audio(audio_ans, format='audio/mp3')
                
                st.session_state.wrong_state = True

        # Nút bỏ qua khi sai
        if st.session_state.get('wrong_state'):
            if st.button("Tiếp tục câu sau ➡️"):
                st.session_state.current_idx += 1
                st.session_state.revealed_indices = set()
                st.session_state.wrong_state = False
                st.rerun()

    else:
        st.success(f"🎉 HOÀN THÀNH! Kết quả: {st.session_state.score}/{len(st.session_state.questions)}")
        if st.button("🔄 Học lại bài này"):
            st.session_state.current_idx = 0
            st.session_state.score = 0
            st.session_state.revealed_indices = set()
            random.shuffle(st.session_state.questions)
            st.rerun()

else:
    st.info("👈 Hãy chọn bài học ở menu bên trái để bắt đầu.")
    st.image("https://cdn-icons-png.flaticon.com/512/3403/3403525.png", width=100)
