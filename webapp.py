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

# --- HÀM HỖ TRỢ ---
def load_data(sheet_name, part=None):
    try:
        # Nếu chọn chế độ ôn tập thì đọc sheet hệ thống
        if sheet_name in [SHEET_REVIEW, SHEET_UNSURE]:
            df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
        else:
            # Chế độ học Unit thường
            df = pd.read_excel(FILE_PATH, sheet_name=sheet_name)
            if part == 1:
                df = df.iloc[:, [0, 1]]
            elif part == 2:
                df = df.iloc[:, [2, 3]]
        
        df.columns = ['Question', 'Answer']
        # Giữ lại cột Source nếu có (để biết nguồn gốc từ đâu)
        if 'Source' not in df.columns:
            df['Source'] = sheet_name

        df = df.dropna(subset=['Question', 'Answer'])
        data = df.to_dict('records')
        random.shuffle(data)
        return data
    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu: {e}")
        return []

def save_unsure_to_excel(card, current_unit, part):
    """Lưu câu chưa chắc vào file Excel"""
    try:
        # Xác định tên nguồn
        source_name = f"{current_unit} (Part {part})" if part else current_unit
        
        new_row = pd.DataFrame([{
            'Question': card['Question'], 
            'Answer': card['Answer'], 
            'Source': source_name
        }])

        # Đọc sheet Unsure hiện tại để nối thêm
        try:
            with pd.ExcelWriter(FILE_PATH, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                # Load sheet cũ để tìm dòng cuối
                try:
                    writer.book = load_workbook(FILE_PATH)
                    # Nếu sheet Unsure đã tồn tại, ta append (cần logic phức tạp hơn chút với openpyxl thuần hoặc pandas)
                    # Để đơn giản và an toàn cho Web App: Ta đọc toàn bộ Unsure ra, cộng thêm, rồi ghi đè lại sheet đó.
                    pass 
                except: pass
        except: pass
        
        # Cách an toàn nhất: Đọc - Gộp - Ghi đè (tránh lỗi permission phức tạp)
        try:
            df_old = pd.read_excel(FILE_PATH, sheet_name=SHEET_UNSURE)
        except:
            df_old = pd.DataFrame(columns=['Question', 'Answer', 'Source'])
            
        df_combined = pd.concat([df_old, new_row]).drop_duplicates(subset=['Question'], keep='last')
        
        with pd.ExcelWriter(FILE_PATH, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_combined.to_excel(writer, sheet_name=SHEET_UNSURE, index=False)
            
        return True
    except Exception as e:
        st.error(f"Không lưu được file (Có thể file đang mở?): {e}")
        return False

def get_audio_html(text):
    try:
        tts = gTTS(text=str(text), lang='en')
        filename = "temp_audio.mp3"
        tts.save(filename)
        audio_file = open(filename, 'rb')
        audio_bytes = audio_file.read()
        return audio_bytes
    except: return None

# --- KHỞI TẠO STATE ---
if 'questions' not in st.session_state: st.session_state.questions = []
if 'current_idx' not in st.session_state: st.session_state.current_idx = 0
if 'score' not in st.session_state: st.session_state.score = 0
if 'revealed_indices' not in st.session_state: st.session_state.revealed_indices = set() # Lưu các vị trí chữ cái đã lật

# --- SIDEBAR ---
st.title("🎓 English Master")
with st.sidebar:
    st.header("Cài đặt")
    try:
        xls = pd.ExcelFile(FILE_PATH)
        # Lọc ra các Unit học và thêm 2 chế độ ôn tập
        sheets = [s for s in xls.sheet_names if s not in [SHEET_REVIEW, SHEET_UNSURE]]
        review_options = ["--- Ôn tập ---", SHEET_REVIEW, SHEET_UNSURE]
    except:
        sheets = []
        review_options = []

    unit_choice = st.selectbox("Chọn Unit:", sheets + review_options)
    
    # Chỉ hiện chọn Part nếu là Unit thường
    selected_part = None
    if unit_choice not in [SHEET_REVIEW, SHEET_UNSURE, "--- Ôn tập ---"]:
        selected_part = st.radio("Chọn phần:", [1, 2], format_func=lambda x: f"Phần {x}")
    
    if st.button("BẮT ĐẦU HỌC 🚀", type="primary"):
        if unit_choice == "--- Ôn tập ---":
            st.warning("Vui lòng chọn Unit hoặc chế độ ôn tập cụ thể.")
        else:
            data = load_data(unit_choice, selected_part)
            if data:
                st.session_state.questions = data
                st.session_state.current_idx = 0
                st.session_state.score = 0
                st.session_state.revealed_indices = set() # Reset gợi ý
                st.rerun()
            else:
                st.warning("Không có dữ liệu!")

# --- MÀN HÌNH HỌC ---
if len(st.session_state.questions) > 0:
    idx = st.session_state.current_idx
    
    if idx < len(st.session_state.questions):
        q_data = st.session_state.questions[idx]
        total = len(st.session_state.questions)
        answer_text = str(q_data['Answer']).strip()
        
        # 1. Thanh tiến trình
        st.progress((idx) / total)
        st.caption(f"Câu {idx + 1}/{total}")

        # 2. Hiển thị câu hỏi & Audio
        col_q, col_audio = st.columns([0.8, 0.2])
        with col_q:
            st.info(f"❓: {q_data['Question']}")
        with col_audio:
            if st.button("🔊", key=f"audio_q_{idx}"):
                audio_bytes = get_audio_html(q_data['Question'])
                if audio_bytes: st.audio(audio_bytes, format='audio/mp3')

        # 3. PHẦN GỢI Ý TƯƠNG TÁC (NEW)
        st.write("Gợi ý (Bấm vào ô để lật chữ):")
        # Tạo các cột nhỏ để chứa nút bấm
        # Streamlit hơi khó căn chỉnh nhiều nút nhỏ, ta dùng cách hiển thị thông minh
        
        # Chia từ thành các ký tự
        cols = st.columns(len(answer_text) if len(answer_text) < 15 else 15) # Giới hạn 15 cột/dòng để đỡ vỡ
        
        # Logic hiển thị gợi ý
        hint_html = ""
        for i, char in enumerate(answer_text):
            if char == " ":
                hint_html += "&nbsp;&nbsp;&nbsp;" # Khoảng trắng
            elif i in st.session_state.revealed_indices:
                hint_html += f"<span style='color:red; font-weight:bold; border:1px solid #ddd; padding:2px 8px; margin:1px; background:#ffeaa7'>{char}</span>"
            else:
                # Nút bấm giả lập bằng HTML hoặc Button của Streamlit
                # Vì Streamlit không cho render quá nhiều button trong loop dễ dàng, 
                # ta dùng cơ chế: Chọn vị trí muốn mở
                hint_html += f"<span style='color:transparent; border:1px solid #999; padding:2px 8px; margin:1px; background:#dfe6e9'>_</span>"
        
        st.markdown(hint_html, unsafe_allow_html=True)

        # Thanh trượt hoặc Selectbox để chọn lật chữ cái (Giải pháp tốt nhất cho Web Mobile)
        # Vì trên điện thoại bấm nút bé xíu rất khó, ta dùng slider hoặc nút "Gợi ý tiếp theo"
        col_hint_btn, col_unsure = st.columns([1, 1])
        
        with col_hint_btn:
            # Nút gợi ý thông minh: Mở ngẫu nhiên 1 ký tự chưa mở
            if st.button("💡 Mở 1 chữ cái"):
                unrevealed = [i for i, c in enumerate(answer_text) if c != " " and i not in st.session_state.revealed_indices]
                if unrevealed:
                    pick = random.choice(unrevealed)
                    st.session_state.revealed_indices.add(pick)
                    st.rerun()

        with col_unsure:
            # 4. TÍNH NĂNG LƯU CHƯA CHẮC (NEW)
            if st.button("💾 Lưu 'Chưa chắc'"):
                if save_unsure_to_excel(q_data, unit_choice, selected_part):
                    st.toast("✅ Đã lưu vào sheet Unsure!", icon="💾")
                else:
                    st.toast("❌ Lỗi lưu file (Hãy đóng file Excel)", icon="⚠️")

        # 5. Nhập liệu
        with st.form(key=f"form_{idx}"):
            user_input = st.text_input("Nhập đáp án:", key=f"input_{idx}")
            submit = st.form_submit_button("Trả lời")
        
        if submit:
            if user_input.strip().lower() == answer_text.lower():
                st.success("✅ CHÍNH XÁC!")
                st.balloons()
                st.session_state.score += 1
                
                # Auto play answer audio (workaround: hiển thị player audio ngay lập tức)
                audio_ans = get_audio_html(answer_text)
                if audio_ans: st.audio(audio_ans, format='audio/mp3')
                
                time.sleep(1.5)
                st.session_state.current_idx += 1
                st.session_state.revealed_indices = set() # Reset gợi ý cho câu mới
                st.rerun()
            else:
                st.error(f"❌ Sai rồi! Đáp án: {answer_text}")
                audio_ans = get_audio_html(answer_text)
                if audio_ans: st.audio(audio_ans, format='audio/mp3')
                
                # Nếu sai, nút tiếp tục xuất hiện bên ngoài form
                st.session_state.wrong_state = True 

        # Nút bỏ qua nếu làm sai
        if 'wrong_state' in st.session_state and st.session_state.wrong_state:
            if st.button("Tiếp tục (Đi câu sau)"):
                st.session_state.current_idx += 1
                st.session_state.revealed_indices = set()
                del st.session_state['wrong_state']
                st.rerun()

    else:
        st.success(f"🎉 HOÀN THÀNH PHIÊN HỌC! Kết quả: {st.session_state.score}/{len(st.session_state.questions)}")
        if st.button("Học lại bài này"):
            st.session_state.current_idx = 0
            st.session_state.score = 0
            st.session_state.revealed_indices = set()
            st.rerun()
else:
    st.info("👈 Hãy chọn Unit bên menu trái và nhấn BẮT ĐẦU.")
    st.markdown("---")
    st.caption("Tips: Dùng điện thoại kết nối cùng Wifi với máy tính để học.")
