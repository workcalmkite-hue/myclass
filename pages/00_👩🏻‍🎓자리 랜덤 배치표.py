import streamlit as st
import pandas as pd
import random
import io
import os

import gspread
from google.oauth2.service_account import Credentials

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# =========================================================
# 0. 스프레드시트 ID (여기만 바꾸면 됨)
# =========================================================
SPREADSHEET_ID = "15c7dqXD7OE87InzW8SMUiSa50mEfp1WNyegTpPWZCMo"


# =========================================================
# 1. 폰트 설정 (MaruBuri)
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    os.path.join(BASE_DIR, "fonts", "MaruBuri-Regular.ttf"),
    os.path.join(BASE_DIR, "fonts", "MaruBuri-Regular.otf"),
    os.path.join(BASE_DIR, "..", "fonts", "MaruBuri-Regular.ttf"),
    os.path.join(BASE_DIR, "..", "fonts", "MaruBuri-Regular.otf"),
]

FONT_PATH = None
for p in FONT_CANDIDATES:
    if os.path.exists(p):
        FONT_PATH = p
        break

KOREAN_FONT = "MaruBuri"
if FONT_PATH:
    try:
        pdfmetrics.registerFont(TTFont(KOREAN_FONT, FONT_PATH))
    except Exception:
        KOREAN_FONT = "Helvetica"
else:
    KOREAN_FONT = "Helvetica"


# =========================================================
# 2. 샘플 데이터 (시트 실패 시)
# =========================================================
def create_sample_students_df():
    data = {
        "출석 번호": list(range(1, 25)),
        "이름": [
            "김철수", "이영희", "박지민", "최민준", "정하늘", "윤서연",
            "강도현", "한지우", "오민재", "서예진", "신현우", "유진아",
            "임태경", "장미나", "전호준", "조아라", "차승원", "허다인",
            "구범수", "나유리", "류준열", "문채원", "변요한", "송혜교",
        ],
        "성별": [
            "M", "F", "F", "M", "M", "F",
            "M", "F", "M", "F", "M", "F",
            "M", "F", "M", "F", "M", "F",
            "M", "F", "M", "F", "M", "F",
        ],
    }
    return pd.DataFrame(data)


# =========================================================
# 3. Google Sheets → 데이터 불러오기
# =========================================================
def load_student_data():
    try:
        service_info = st.secrets["gcp_service_account"]
    except Exception:
        st.error("❌ secrets에 [gcp_service_account]가 없습니다.")
        return create_sample_students_df()

    try:
        creds = Credentials.from_service_account_info(
            service_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        client = gspread.authorize(creds)

        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.sheet1
        records = ws.get_all_records()

        if not records:
            st.warning("⚠️ 시트에 데이터가 없습니다.")
            return create_sample_students_df()

        df = pd.DataFrame(records)

        # 필수 컬럼이 있는지 확인 (출석 번호 / 이름 / 성별 or 변형)
        cols = df.columns
        has_num = any(c in cols for c in ["출석 번호", "번호", "Number", "NO", "No"])
        has_name = any(c in cols for c in ["이름", "Name", "학생명", "성명"])
        has_gender = any(c in cols for c in ["성별", "Gender", "gender", "sex", "Sex"])

        if not (has_num and has_name and has_gender):
            st.error("❌ '출석 번호/번호', '이름', '성별' 컬럼을 찾지 못했습니다.")
            return create_sample_students_df()

        return df

    except Exception as e:
        st.error(f"❌ Google Sheets 오류: {e}")
        return create_sample_students_df()


STUDENTS_DF = load_student_data()
STUDENTS_LIST = STUDENTS_DF.to_dict("records")


# =========================================================
# 4. 학생 dict → 좌석 표시용 dict 변환
# =========================================================
def student_to_seat(student: dict):
    if student is None:
        return None

    # --- 성별 인식 (여러 케이스)
    gender = (
        student.get("Gender")
        or student.get("성별")
        or student.get("gender")
        or student.get("Sex")
        or ""
    )
    gender = str(gender).strip()

    if gender in ["F", "여", "여자", "f", "female", "FEMALE"]:
        color = "#F5B7B1"  # 여
    elif gender in ["M", "남", "남자", "m", "male", "MALE"]:
        color = "#A9CCE3"  # 남
    else:
        color = "#e5e7eb"

    # --- 번호 인식
    number = (
        student.get("Number")
        or student.get("출석 번호")
        or student.get("번호")
        or student.get("NO")
        or student.get("No")
        or ""
    )

    # --- 이름 인식
    name = (
        student.get("Name")
        or student.get("이름")
        or student.get("학생명")
        or student.get("성명")
        or ""
    )

    num_str = str(number).strip()
    name_str = str(name).strip()

    label = f"{num_str} {name_str}".strip()
    return {"name": label, "color": color}


# =========================================================
# 5. 좌석 배치 로직 (Single / Paired)
# =========================================================
def assign_seats(student_list, rows, bun_dan, mode):
    students = student_list[:]
    random.shuffle(students)

    if mode == "Paired":
        cols = bun_dan * 2  # 한 모둠에 2자리
    else:
        cols = bun_dan

    total_seats = rows * cols
    students = students[:total_seats]

    if mode == "Paired":
        pairs = []
        for i in range(0, len(students), 2):
            s1 = student_to_seat(students[i])
            s2 = student_to_seat(students[i + 1]) if i + 1 < len(students) else None
            pairs.append((s1, s2))

        seat_matrix = []
        idx = 0
        for _ in range(rows):
            row = []
            for _ in range(bun_dan):
                if idx < len(pairs):
                    s1, s2 = pairs[idx]
                    row.append(s1)
                    row.append(s2)
                else:
                    row.append(None)
                    row.append(None)
                idx += 1
            seat_matrix.append(row)
        return seat_matrix

    else:
        seat_matrix = []
        idx = 0
        for _ in range(rows):
            row = []
            for _ in range(cols):
                if idx < len(students):
                    row.append(student_to_seat(students[idx]))
                else:
                    row.append(None)
                idx += 1
            seat_matrix.append(row)
        return seat_matrix


# =========================================================
# 6. HTML 렌더링 (화면용)
# =========================================================
HTML_STYLE = """
<style>
    .desk-grid {
        display: grid;
        gap: 10px;
        padding: 20px;
        background-color: #f4f4f9;
        border-radius: 12px;
        width: fit-content;
    }
    .desk {
        width: 120px;
        height: 58px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        font-size: 15px;
        padding: 4px;
        border: 2px solid #555;
    }
    .empty-desk {
        background-color: #e0e7ff;
        border-style: dashed;
        color: #9ca3af;
    }
    .front-of-class {
        font-size: 1.6em;
        font-weight: 900;
        color: #2563eb;
        border: 3px solid #2563eb;
        padding: 8px 16px;
        border-radius: 12px;
        background-color: #eff6ff;
        display: inline-block;
    }
</style>
"""


def render_chart(matrix, view_mode, bun_dan, seating_mode):
    if view_mode == "teacher":
        matrix = matrix[::-1]

    cols = len(matrix[0])
    extra_pairs = (cols // 2 - 1) if seating_mode == "Paired" else 0
    grid_cols = cols + max(0, extra_pairs)

    html = f'<div class="desk-grid" style="grid-template-columns: repeat({grid_cols}, auto);">'

    for row in matrix:
        for i, desk in enumerate(row):
            classes = "desk"
            if desk:
                style = f"background-color:{desk['color']};border-color:{desk['color']};"
                name = desk["name"]
            else:
                classes += " empty-desk"
                style = ""
                name = "빈 자리"

            html += f'<div class="{classes}" style="{style}">{name}</div>'

            if seating_mode == "Paired" and i % 2 == 1 and i != len(row) - 1:
                html += '<div style="width:20px;"></div>'

    html += "</div>"
    return html


# =========================================================
# 7. PDF 생성 (중앙 정렬 + 교탁 안 겹치게)
# =========================================================
def draw_pdf_page(c, matrix, seating_mode, view_mode, bun_dan, title):
    width, height = landscape(A4)

    # 제목
    c.setFont(KOREAN_FONT, 26)
    c.drawCentredString(width / 2, height - 40, title)

    # 교사용은 앞줄이 아래에 오도록 뒤집어서, 학생용은 그대로
    if view_mode == "teacher":
        matrix_to_draw = matrix[::-1]
    else:
        matrix_to_draw = matrix

    rows = len(matrix_to_draw)
    cols = len(matrix_to_draw[0])

    margin_y = 80
    gap_x = 10
    gap_y = 18
    pair_gap = 22 if seating_mode == "Paired" else 0

    # 1) 세로 방향: 위쪽에 제목 + 여백, 그 아래부터 책상
    available_h = height - margin_y * 2 - 80
    cell_h = (available_h - gap_y * (rows - 1)) / rows if rows > 0 else 40
    start_y = height - margin_y - cell_h  # 첫 줄 y 위치

    # 2) 가로 방향: 전체 폭 계산 후 중앙 정렬
    #   전체 책상 폭 = (cols * cell_w) + (cols-1)*gap_x + (bun_dan-1)*pair_gap
    #   이 식을 width에 딱 맞춰 cell_w를 계산
    total_base_gaps = (cols - 1) * gap_x
    total_pair_gaps = (bun_dan - 1) * pair_gap if seating_mode == "Paired" else 0

    available_w = width - 80  # 좌우 여백 합 약 80
    cell_w = (available_w - total_base_gaps - total_pair_gaps) / cols if cols > 0 else 40

    total_width = cols * cell_w + total_base_gaps + total_pair_gaps
    start_x = (width - total_width) / 2  # 중앙 정렬 시작점

    # 3) 책상 그리기
    for r, row in enumerate(matrix_to_draw):
        y = start_y - r * (cell_h + gap_y)
        x = start_x

        for c_idx, desk in enumerate(row):
            if desk:
                c.setFillColor(HexColor(desk["color"]))
                c.setStrokeColor(HexColor(desk["color"]))
            else:
                c.setFillColor(HexColor("#e0e7ff"))
                c.setStrokeColor(HexColor("#d1d5db"))

            c.rect(x, y, cell_w, cell_h, fill=1, stroke=1)

            c.setFillColor(black)
            if desk:
                c.setFont(KOREAN_FONT, 16)
                c.drawCentredString(x + cell_w / 2, y + cell_h / 2 - 5, desk["name"])
            else:
                c.setFont(KOREAN_FONT, 14)
                c.drawCentredString(x + cell_w / 2, y + cell_h / 2 - 5, "빈 자리")

            x += cell_w + gap_x

            if seating_mode == "Paired" and c_idx % 2 == 1 and c_idx != cols - 1:
                x += pair_gap

    # 4) 교탁: 항상 맨 아래 중앙 (학생용에서도 글자와 절대 안 겹치게)
    desk_w = 130
    desk_h = 48
    desk_x = width / 2 - desk_w / 2
    desk_y = margin_y - desk_h  # 페이지 아래쪽

    c.setFillColor(HexColor("#eff6ff"))
    c.setStrokeColor(HexColor("#2563eb"))
    c.rect(desk_x, desk_y, desk_w, desk_h, fill=1, stroke=1)
    c.setFont(KOREAN_FONT, 18)
    c.setFillColor(HexColor("#2563eb"))
    c.drawCentredString(desk_x + desk_w / 2, desk_y + desk_h / 2 - 4, "교탁")


def make_pdf(matrix, seating_mode, view_mode, bun_dan, title):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    draw_pdf_page(c, matrix, seating_mode, view_mode, bun_dan, title)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


def make_pdf_both(matrix, seating_mode, bun_dan):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    draw_pdf_page(c, matrix, seating_mode, "teacher", bun_dan, "교사용 좌석 배치표")
    c.showPage()

    draw_pdf_page(c, matrix, seating_mode, "student", bun_dan, "학생용 좌석 배치표")
    c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue()


# =========================================================
# 8. Streamlit UI
# =========================================================
st.markdown(HTML_STYLE, unsafe_allow_html=True)
st.title("🧑‍🏫 자리 랜덤 배치표 (Google Sheets 연동)")

with st.expander("불러온 학생 명단 확인"):
    st.dataframe(STUDENTS_DF)

col1, col2 = st.columns(2)
with col1:
    seating_mode = st.radio(
        "좌석 형태 선택",
        ["Single", "Paired"],
        format_func=lambda x: "혼자 앉기" if x == "Single" else "짝으로 앉기",
    )
with col2:
    bun_dan = st.number_input("분단 수", min_value=2, max_value=10, value=5 if seating_mode == "Paired" else 4)
    rows = st.number_input("줄 수(행)", min_value=2, max_value=10, value=6)


if st.button("🎉 좌석 배치 생성", type="primary"):
    if seating_mode == "Paired":
        seats_per_row = int(bun_dan) * 2
    else:
        seats_per_row = int(bun_dan)

    total_seats = int(rows) * seats_per_row
    num_students = len(STUDENTS_LIST)

    if total_seats < num_students:
        st.error("⚠️ 좌석이 부족해요!")
        st.warning(f"학생 {num_students}명 / 자리 {total_se츠}석")
    else:
        matrix = assign_seats(STUDENTS_LIST, int(rows), int(bun_dan), seating_mode)
        st.session_state["matrix"] = matrix
        st.session_state["bun_dan"] = int(bun_dan)
        st.session_state["mode"] = seating_mode
        st.success("좌석 배치가 성공적으로 생성되었습니다!")


if "matrix" in st.session_state:
    matrix = st.session_state["matrix"]
    bun_dan = st.session_state["bun_dan"]
    seating_mode = st.session_state["mode"]

    st.markdown("---")
    st.header("1️⃣ 교사 시야 (교탁 입장 기준)")
    st.markdown(
        render_chart(matrix, "teacher", bun_dan, seating_mode),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="text-align:center;"><span class="front-of-class">교탁</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.header("2️⃣ 학생 시야 (학생용 안내)")
    st.markdown(
        '<div style="text-align:center;"><span class="front-of-class">교탁</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        render_chart(matrix, "student", bun_dan, seating_mode),
        unsafe_allow_html=True,
    )

    # PDF 다운로드
    teacher_pdf = make_pdf(matrix, seating_mode, "teacher", bun_dan, "교사용 좌석 배치표")
    student_pdf = make_pdf(matrix, seating_mode, "student", bun_dan, "학생용 좌석 배치표")
    both_pdf = make_pdf_both(matrix, seating_mode, bun_dan)

    st.markdown("---")
    st.subheader("📄 PDF 다운로드")

    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "📥 교사용 PDF",
            teacher_pdf,
            file_name="seating_teacher.pdf",
            mime="application/pdf",
        )
    with d2:
        st.download_button(
            "📥 학생용 PDF",
            student_pdf,
            file_name="seating_student.pdf",
            mime="application/pdf",
        )
    with d3:
        st.download_button(
            "📥 교사+학생 한 번에",
            both_pdf,
            file_name="seating_both.pdf",
            mime="application/pdf",
        )

# 범례
st.markdown("---")
st.subheader("🌈 성별 색상 안내")
cA, cB, cC = st.columns(3)
with cA:
    st.markdown(
        '<div class="desk" style="background:#F5B7B1;border-color:#F5B7B1;">여학생</div>',
        unsafe_allow_html=True,
    )
with cB:
    st.markdown(
        '<div class="desk" style="background:#A9CCE3;border-color:#A9CCE3;">남학생</div>',
        unsafe_allow_html=True,
    )
with cC:
    st.markdown(
        '<div class="desk empty-desk">빈 자리</div>',
        unsafe_allow_html=True,
    )

st.caption("이름은 ‘번호 이름’ 형식으로 표시됩니다. (예: 3 김미연)")
