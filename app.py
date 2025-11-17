import streamlit as st
import pandas as pd
import random
import io
import os

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import gspread
from google.oauth2.service_account import Credentials


# =========================
# 0. 한글 폰트 등록 (MaruBuri)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# otf / ttf 둘 다 탐색 (있는 것 먼저 사용)
FONT_CANDIDATES = [
    os.path.join(BASE_DIR, "fonts", "MaruBuri-Regular.otf"),
    os.path.join(BASE_DIR, "fonts", "MaruBuri-Regular.ttf"),
]

FONT_PATH = None
for path in FONT_CANDIDATES:
    if os.path.exists(path):
        FONT_PATH = path
        break

KOREAN_FONT_NAME = "MaruBuri"

if FONT_PATH:
    pdfmetrics.registerFont(TTFont(KOREAN_FONT_NAME, FONT_PATH))
else:
    print("⚠️ Korean font file not found in fonts/MaruBuri-Regular.otf or .ttf")


# =========================
# 1. Google Sheets 학생 데이터 로드
# =========================
def load_student_data():
    """
    Streamlit secrets에 gcp_service_account, spreadsheet_id가 들어있다고 가정.
    (설정은 Settings → Secrets에 넣어둔 상태)
    """
    try:
        sa_info = st.secrets["gcp_service_account"]
        spreadsheet_id = st.secrets["spreadsheet_id"]
    except Exception as e:
        st.error("❌ Streamlit secrets에 'gcp_service_account'와 'spreadsheet_id'가 설정되어 있는지 확인해 주세요.")
        raise e

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    client = gspread.authorize(creds)

    # 스프레드시트 열기
    sh = client.open_by_key(spreadsheet_id)

    # 기본: 첫 번째 시트 사용 (원하면 worksheet 이름으로 변경 가능)
    ws = sh.sheet1
    # ws = sh.worksheet("1반")  # 특정 시트명을 쓰고 싶으면 주석 해제 후 이름 수정

    records = ws.get_all_records()
    if not records:
        st.warning("⚠️ 구글 시트에 데이터가 없습니다.")
        return pd.DataFrame(columns=["Number", "Name", "Gender"])

    df = pd.DataFrame(records)

    # 컬럼 이름 자동 매핑
    col_num_candidates = ["Number", "번호", "NO", "No", "no", "Num"]
    col_name_candidates = ["Name", "이름"]
    col_gender_candidates = ["Gender", "성별", "gender", "sex", "Sex"]

    def find_col(candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    col_num = find_col(col_num_candidates)
    col_name = find_col(col_name_candidates)
    col_gender = find_col(col_gender_candidates)

    rename_map = {}
    if col_num and col_num != "Number":
        rename_map[col_num] = "Number"
    if col_name and col_name != "Name":
        rename_map[col_name] = "Name"
    if col_gender and col_gender != "Gender":
        rename_map[col_gender] = "Gender"

    if rename_map:
        df = df.rename(columns=rename_map)

    needed_cols = []
    for c in ["Number", "Name", "Gender"]:
        if c in df.columns:
            needed_cols.append(c)
        else:
            st.warning(f"⚠️ 구글 시트에 '{c}' 컬럼이 없습니다. (선택적으로만 사용됩니다)")

    if not needed_cols:
        st.error("❌ 'Number', 'Name', 'Gender' 중 하나도 찾지 못했습니다. 시트 헤더를 확인해 주세요.")
        return pd.DataFrame(columns=["Number", "Name", "Gender"])

    df = df[needed_cols]

    # Number가 문자열이면 숫자로 변환 시도
    if "Number" in df.columns:
        df["Number"] = pd.to_numeric(df["Number"], errors="coerce").fillna(df["Number"])

    return df


STUDENTS_DF = load_student_data()
STUDENTS_LIST = STUDENTS_DF.to_dict("records")


# =========================
# 2. 헬퍼: 학생 dict → 좌석 dict (색 + 이름 변환)
# =========================
def student_to_seat(student: dict):
    if student is None:
        return None
    gender = str(student.get("Gender", "")).strip()
    if gender in ["F", "여", "여자"]:
        color = "#F5B7B1"  # 여학생 핑크
    elif gender in ["M", "남", "남자"]:
        color = "#A9CCE3"  # 남학생 블루
    else:
        color = "#e5e7eb"  # 기타/미지정

    label = f"{student.get('Number', '')} {student.get('Name', '')}".strip()
    return {"name": label, "color": color}


# =========================
# 3. 좌석 배치 함수
# =========================
def assign_seats(student_list, rows, bun_dan, mode):
    """
    student_list: [{Number, Name, Gender}, ...]
    rows: 줄 수
    bun_dan: 분단 수 (짝 모드일 때 실제 열은 bun_dan * 2)
    mode: 'Single' 또는 'Paired'
    """
    pair_mode = mode == "Paired"

    students = student_list[:]
    random.shuffle(students)

    if pair_mode:
        seats_per_row = bun_dan * 2
    else:
        seats_per_row = bun_dan

    total_seats = rows * seats_per_row
    if len(students) > total_seats:
        students = students[:total_seats]

    # 짝으로 앉기
    if pair_mode:
        pairs = []
        for i in range(0, len(students), 2):
            s1 = student_to_seat(students[i])
            s2 = student_to_seat(students[i + 1]) if i + 1 < len(students) else None
            pairs.append((s1, s2))

        seat_matrix = []
        pair_idx = 0
        for _ in range(rows):
            row_data = []
            for _ in range(bun_dan):  # 각 분단은 2자리
                if pair_idx < len(pairs):
                    s1, s2 = pairs[pair_idx]
                    row_data.append(s1)  # 왼쪽
                    row_data.append(s2)  # 오른쪽
                else:
                    row_data.append(None)
                    row_data.append(None)
                pair_idx += 1
            seat_matrix.append(row_data)
        return seat_matrix

    # 혼자 앉기
    else:
        seat_students = [student_to_seat(s) for s in students]
        seat_matrix = []
        idx = 0
        for _ in range(rows):
            row_data = []
            for _ in range(seats_per_row):
                if idx < len(seat_students):
                    row_data.append(seat_students[idx])
                else:
                    row_data.append(None)
                idx += 1
            seat_matrix.append(row_data)
        return seat_matrix


# =========================
# 4. HTML / CSS 렌더링 (화면용)
# =========================
HTML_STYLE = """
<style>
    .seating-chart-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100%;
        margin-bottom: 30px;
    }
    .desk-grid {
        display: grid;
        gap: 10px;
        padding: 20px;
        background-color: #f4f4f9;
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        width: fit-content;
    }
    .desk {
        width: 120px;
        height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        font-size: 14px;
        padding: 5px;
        border: 2px solid #555;
        color: #1f2937;
        box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        transition: transform 0.1s ease;
    }
    .empty-desk {
        background-color: #e0e7ff;
        border-style: dashed;
        color: #9ca3af;
    }
    .paired-desk-left {
        border-right: none !important;
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
    }
    .paired-desk-right {
        border-left: 1px dashed #555 !important;
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
        margin-left: -1px;
    }
    .front-of-class {
        font-size: 1.5em;
        font-weight: 900;
        color: #2563eb;
        margin-bottom: 15px;
        padding: 10px 20px;
        border: 4px solid #2563eb;
        border-radius: 15px;
        background-color: #eff6ff;
        display: inline-block;
    }
    @media (max-width: 600px) {
        .desk {
            width: 80px;
            height: 45px;
            font-size: 12px;
        }
        .front-of-class {
            font-size: 1.2em;
        }
    }
</style>
"""


def render_chart(matrix, view_mode, bun_dan, seating_mode):
    """
    matrix: 2D list (원소: {'name','color'} or None)
    view_mode: 'teacher' / 'student'
    bun_dan: 분단 수
    seating_mode: 'Single' / 'Paired'
    """
    rows = len(matrix)
    if rows == 0:
        return "<div>데이터 없음</div>"

    cols = len(matrix[0])

    # 교사용: 교탁에서 볼 때 앞줄이 아래 → 행 순서 뒤집어서 표시
    # 학생용: 종이로 볼 때 앞줄이 위 → 원래 순서
    display_matrix = matrix[::-1] if view_mode == "teacher" else matrix

    grid_style = f"grid-template-columns: repeat({cols}, auto);"
    html_content = f'<div class="desk-grid" style="{grid_style}">'
    is_paired_mode = seating_mode == "Paired"

    for row in display_matrix:
        for c_idx, desk in enumerate(row):
            desk_class = "desk"
            desk_style = ""
            name_content = ""

            extra_margin = ""
            if is_paired_mode:
                # 모양 C: 각각 독립 책상, 다만 짝(2개) 단위로 분단 간격만 추가
                if c_idx % 2 == 1 and c_idx != len(row) - 1:
                    # 짝의 오른쪽 책상 뒤에 분단 간격
                    extra_margin = "margin-right: 20px;"

            if desk:
                desk_style = f"background-color: {desk['color']}; border-color: {desk['color']};"
                name_content = desk["name"]
            else:
                desk_class += " empty-desk"
                desk_style = "border-color: #d1d5db;"
                name_content = "빈 자리"

            full_style = desk_style + extra_margin
            html_content += f'<div class="{desk_class}" style="{full_style}">{name_content}</div>'

    html_content += "</div>"
    return html_content


# =========================
# 5. PDF 그리기 (모양 C, 폰트 +2, 간격 넓게)
# =========================
def draw_seating_page(c, seating_matrix, seating_mode, view_mode, bun_dan, title_text):
    width, height = landscape(A4)

    # 제목 폰트 크게
    c.setFont(KOREAN_FONT_NAME, 24)
    c.drawCentredString(width / 2, height - 50, title_text)

    rows = len(seating_matrix)
    cols = len(seating_matrix[0]) if rows > 0 else 0

    # 교사용: 앞줄이 아래 → 행 역순
    # 학생용: 앞줄이 위 → 그대로
    matrix = seating_matrix[::-1] if view_mode == "teacher" else seating_matrix

    margin_x = 50
    margin_y = 90

    # 책상 크기 작게, 간격 넓게
    seat_gap_x = 15   # 가로 여백
    seat_gap_y = 20   # 세로 여백

    # 세로 방향 크기 계산
    available_height = height - margin_y * 2 - 70
    if rows > 0:
        cell_h = (available_height - seat_gap_y * (rows - 1)) / rows
    else:
        cell_h = 35

    # 가로 방향 크기 계산
    if cols > 0:
        if seating_mode == "Paired":
            # 모양 C: 전체 열 수 = cols, 분단 수 = bun_dan = cols/2
            pairs = cols // 2
            pair_gap = 20  # 분단 간 간격
            total_pair_gaps = max(0, pairs - 1) * pair_gap
            total_seat_gaps = (cols - 1) * seat_gap_x
            available_width = width - margin_x * 2 - total_pair_gaps - total_seat_gaps
            cell_w = available_width / cols
        else:
            # Single: 일반적인 grid
            total_seat_gaps = (cols - 1) * seat_gap_x
            available_width = width - margin_x * 2 - total_seat_gaps
            cell_w = available_width / cols
    else:
        cell_w = 35

    start_y = height - margin_y - cell_h

    # 좌석 그리기
    for r, row in enumerate(matrix):
        y = start_y - r * (cell_h + seat_gap_y)
        x = margin_x

        if seating_mode == "Paired":
            # 각 행에서 짝(2칸)을 기준으로 분단 간격 추가
            for c_idx, seat in enumerate(row):
                # 앞 자리가 아니면 기본 가로 간격 추가
                if c_idx > 0:
                    x += seat_gap_x
                # 짝의 오른쪽 자리 뒤에는 분단 간격 추가
                if c_idx % 2 == 0:
                    pass
                else:
                    # 오른쪽 자리 이후 + 분단 간 여백 (마지막 짝 제외)
                    pair_index = c_idx // 2
                    if pair_index < (cols // 2) - 1:
                        # 여분 여백은 다음 반복에서 seat_gap_x와 함께 적용되므로,
                        # 여기서 pair_gap을 미리 더해준다
                        pass

                # 실제 좌표 계산에서 pair_gap 반영
                # (pair_index 기반으로 누적해서 계산하는 구조보다 단순하게 구현)
                # → 위에서 pair_gap을 바로 더하지 않고,
                #   아래에서 짝의 오른쪽일 때 직접 더해주자.
                # 다시 좌표를 재조정
                # (간단화를 위해 이 부분을 다시 작성)
            # 위 loop를 다시 명확하게 작성
            x = margin_x
            c_idx = 0
            while c_idx < cols:
                # 왼쪽 책상
                seat_left = row[c_idx]
                # 오른쪽 책상(없을 수도 있음)
                seat_right = row[c_idx + 1] if c_idx + 1 < cols else None

                # 왼쪽 책상 그리기
                if seat_left:
                    c.setFillColor(HexColor(seat_left["color"]))
                    c.setStrokeColor(HexColor(seat_left["color"]))
                else:
                    c.setFillColor(HexColor("#e0e7ff"))
                    c.setStrokeColor(HexColor("#d1d5db"))

                c.rect(x, y, cell_w, cell_h, fill=1, stroke=1)
                c.setFillColor(black)
                if seat_left:
                    c.setFont(KOREAN_FONT_NAME, 13)
                    c.drawCentredString(
                        x + cell_w / 2,
                        y + cell_h / 2 - 4,
                        seat_left["name"],
                    )
                else:
                    c.setFont(KOREAN_FONT_NAME, 12)
                    c.drawCentredString(
                        x + cell_w / 2,
                        y + cell_h / 2 - 4,
                        "빈 자리",
                    )

                # 오른쪽 책상 위치
                x_right = x + cell_w + seat_gap_x

                if seat_right is not None:
                    if seat_right:
                        c.setFillColor(HexColor(seat_right["color"]))
                        c.setStrokeColor(HexColor(seat_right["color"]))
                    else:
                        c.setFillColor(HexColor("#e0e7ff"))
                        c.setStrokeColor(HexColor("#d1d5db"))

                    c.rect(x_right, y, cell_w, cell_h, fill=1, stroke=1)
                    c.setFillColor(black)
                    if seat_right:
                        c.setFont(KOREAN_FONT_NAME, 13)
                        c.drawCentredString(
                            x_right + cell_w / 2,
                            y + cell_h / 2 - 4,
                            seat_right["name"],
                        )
                    else:
                        c.setFont(KOREAN_FONT_NAME, 12)
                        c.drawCentredString(
                            x_right + cell_w / 2,
                            y + cell_h / 2 - 4,
                            "빈 자리",
                        )

                # 다음 짝의 시작 x:
                # 오른쪽 책상 기준 + cell_w + 분단 간격
                x = x_right + cell_w + 20  # 20 = 분단 간격
                c_idx += 2

        else:
            # Single 모드: 일반적인 그리드
            for c_idx, seat in enumerate(row):
                if c_idx > 0:
                    x += seat_gap_x

                if seat:
                    c.setFillColor(HexColor(seat["color"]))
                    c.setStrokeColor(HexColor(seat["color"]))
                else:
                    c.setFillColor(HexColor("#e0e7ff"))
                    c.setStrokeColor(HexColor("#d1d5db"))

                c.rect(x, y, cell_w, cell_h, fill=1, stroke=1)

                c.setFillColor(black)
                if seat:
                    c.setFont(KOREAN_FONT_NAME, 13)
                    c.drawCentredString(
                        x + cell_w / 2,
                        y + cell_h / 2 - 4,
                        seat["name"],
                    )
                else:
                    c.setFont(KOREAN_FONT_NAME, 12)
                    c.drawCentredString(
                        x + cell_w / 2,
                        y + cell_h / 2 - 4,
                        "빈 자리",
                    )

                x += cell_w

    # 교탁 위치
    desk_w = 110
    desk_h = 45
    desk_x = width / 2 - desk_w / 2

    if view_mode == "teacher":
        # 교사용: 교탁이 아래쪽
        desk_y = margin_y - desk_h - 10
    else:
        # 학생용: 교탁이 위쪽
        desk_y = height - margin_y + 5

    c.setFillColor(HexColor("#eff6ff"))
    c.setStrokeColor(HexColor("#2563eb"))
    c.rect(desk_x, desk_y, desk_w, desk_h, fill=1, stroke=1)
    c.setFont(KOREAN_FONT_NAME, 16)
    c.setFillColor(HexColor("#2563eb"))
    c.drawCentredString(
        desk_x + desk_w / 2,
        desk_y + desk_h / 2 - 4,
        "교탁",
    )


def generate_pdf(seating_matrix, seating_mode, view_mode, bun_dan, title_text="좌석 배치표"):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    draw_seating_page(c, seating_matrix, seating_mode, view_mode, bun_dan, title_text)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_both_pdf(seating_matrix, seating_mode, bun_dan):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    # 1페이지: 교사용
    draw_seating_page(c, seating_matrix, seating_mode, "teacher", bun_dan, "교사용 좌석 배치표")
    c.showPage()
    # 2페이지: 학생용
    draw_seating_page(c, seating_matrix, seating_mode, "student", bun_dan, "학생용 좌석 배치표")
    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# =========================
# 6. Streamlit UI
# =========================
st.set_page_config(layout="centered", page_title="랜덤 좌석배치표 생성기")
st.markdown(HTML_STYLE, unsafe_allow_html=True)

st.title("🧑‍🏫 중학교 랜덤 좌석 배치표 생성기")
st.write("구글 시트의 학생 데이터를 불러와 행/분단 수를 지정하면, 무작위 좌석 배치표를 만들고 PDF로 저장할 수 있어요.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. 좌석 형태 선택")
    seating_mode = st.radio(
        "짝으로 앉을까요, 혼자 앉을까요?",
        ("Single", "Paired"),
        index=0,
        format_func=lambda x: "혼자 앉기 (Single)" if x == "Single" else "짝으로 앉기 (Paired)",
    )

with col2:
    st.subheader("2. 교실 크기 (행 / 분단 수)")
    input_cols = st.number_input(
        "분단 수:",
        min_value=2,
        max_value=10,
        value=4,
        step=1,
    )
    input_rows = st.number_input(
        "줄 수 (행):",
        min_value=2,
        max_value=10,
        value=5,
        step=1,
    )

# ===== 좌석 생성 버튼 =====
if st.button("🎉 좌석 배치표 생성", type="primary"):
    if seating_mode == "Paired":
        seats_per_row = int(input_cols) * 2
    else:
        seats_per_row = int(input_cols)

    total_desks = int(input_rows) * seats_per_row
    num_students = len(STUDENTS_LIST)

    if total_desks < num_students:
        st.error("⚠️ 좌석이 부족합니다!")
        st.warning(f"학생 {num_students}명, 자리 {total_desks}석입니다. 줄/분단 수를 늘려주세요.")
    else:
        seating_matrix = assign_seats(
            STUDENTS_LIST,
            rows=int(input_rows),
            bun_dan=int(input_cols),
            mode=seating_mode,
        )
        st.session_state["seating_matrix"] = seating_matrix
        st.session_state["seating_mode"] = seating_mode
        st.session_state["input_cols"] = int(input_cols)
        st.session_state["input_rows"] = int(input_rows)
        st.success(f"총 {num_students}명을 {int(input_rows)}줄, {int(input_cols)}분단에 배치했습니다.")

# ===== 좌석 결과 + PDF 버튼 (session_state 기반) =====
if "seating_matrix" in st.session_state:
    seating_matrix = st.session_state["seating_matrix"]
    seating_mode_saved = st.session_state["seating_mode"]
    input_cols_saved = st.session_state["input_cols"]
    input_rows_saved = st.session_state["input_rows"]

    st.markdown("---")
    # 교사용: 교탁이 아래 / 앞줄이 아래
    st.header("1️⃣ 교사 시야 (교탁에서 아이들을 바라볼 때)")
    st.markdown(
        render_chart(seating_matrix, "teacher", input_cols_saved, seating_mode_saved),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="text-align:center; margin-top: 15px;"><div class="front-of-class">교탁 (Front of Class)</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    # 학생용: 교탁이 위 / 앞줄이 위
    st.header("2️⃣ 학생 시야 (학생들에게 나누어줄 때)")
    st.markdown(
        '<div style="text-align:center;"><div class="front-of-class">교탁 (Front of Class)</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        render_chart(seating_matrix, "student", input_cols_saved, seating_mode_saved),
        unsafe_allow_html=True,
    )

    # PDF 생성
    teacher_pdf_bytes = generate_pdf(
        seating_matrix,
        seating_mode_saved,
        view_mode="teacher",
        bun_dan=input_cols_saved,
        title_text="교사용 좌석 배치표",
    )
    student_pdf_bytes = generate_pdf(
        seating_matrix,
        seating_mode_saved,
        view_mode="student",
        bun_dan=input_cols_saved,
        title_text="학생용 좌석 배치표",
    )
    both_pdf_bytes = generate_both_pdf(
        seating_matrix,
        seating_mode_saved,
        bun_dan=input_cols_saved,
    )

    st.markdown("---")
    st.subheader("📄 PDF로 저장하기")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "📥 교사용 PDF 다운로드",
            data=teacher_pdf_bytes,
            file_name="seating_teacher.pdf",
            mime="application/pdf",
        )
    with c2:
        st.download_button(
            "📥 학생용 PDF 다운로드",
            data=student_pdf_bytes,
            file_name="seating_student.pdf",
            mime="application/pdf",
        )
    with c3:
        st.download_button(
            "📥 교사+학생용 PDF 한 번에",
            data=both_pdf_bytes,
            file_name="seating_both.pdf",
            mime="application/pdf",
        )

# 범례
st.markdown("---")
st.subheader("🌈 배치 범례")
col_legend_f, col_legend_m, col_legend_p = st.columns(3)

with col_legend_f:
    st.markdown(
        '<div class="desk" style="background-color: #F5B7B1; border-color: #F5B7B1;">여자 학생 (Pink)</div>',
        unsafe_allow_html=True,
    )
with col_legend_m:
    st.markdown(
        '<div class="desk" style="background-color: #A9CCE3; border-color: #A9CCE3;">남자 학생 (Blue)</div>',
        unsafe_allow_html=True,
    )
with col_legend_p:
    st.markdown(
        '<div class="desk empty-desk" style="border-color: #d1d5db;">빈 자리</div>',
        unsafe_allow_html=True,
    )

st.caption("학생 이름은 '번호 이름' 형태로 표시됩니다. (예: 1 홍길동)")
