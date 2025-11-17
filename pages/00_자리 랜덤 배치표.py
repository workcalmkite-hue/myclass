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


# =====================================
# 0. 폰트 설정 (MaruBuri → 없으면 기본)
# =====================================
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

KOREAN_FONT_NAME = "MaruBuri"
if FONT_PATH:
    try:
        pdfmetrics.registerFont(TTFont(KOREAN_FONT_NAME, FONT_PATH))
    except Exception:
        KOREAN_FONT_NAME = "Helvetica"
else:
    KOREAN_FONT_NAME = "Helvetica"


# =====================================
# 1. 샘플 데이터 (시트 실패 시)
# =====================================
def create_sample_students_df():
    data = {
        "Number": list(range(1, 25)),
        "Name": [
            "김철수", "이영희", "박지민", "최민준", "정하늘", "윤서연",
            "강도현", "한지우", "오민재", "서예진", "신현우", "유진아",
            "임태경", "장미나", "전호준", "조아라", "차승원", "허다인",
            "구범수", "나유리", "류준열", "문채원", "변요한", "송혜교",
        ],
        "Gender": [
            "M", "F", "F", "M", "M", "F",
            "M", "F", "M", "F", "M", "F",
            "M", "F", "M", "F", "M", "F",
            "M", "F", "M", "F", "M", "F",
        ],
    }
    return pd.DataFrame(data)


# =====================================
# 2. Google Sheets 에서 학생 데이터 불러오기
# =====================================
def load_student_data():
    try:
        sa_info = st.secrets["gcp_service_account"]
    except Exception:
        st.error("❌ secrets에 [gcp_service_account]가 없습니다. Settings → Secrets 확인해 주세요.")
        return create_sample_students_df()

    spreadsheet_id = st.secrets.get("spreadsheet_id", None)
    if spreadsheet_id is None and isinstance(sa_info, dict):
        spreadsheet_id = sa_info.get("spreadsheet_id", None)

    if spreadsheet_id is None:
        st.error(
            "❌ secrets에서 spreadsheet_id를 찾지 못했습니다.\n\n"
            "아래 둘 중 하나로 설정해 주세요.\n"
            "1) 루트에: spreadsheet_id = \"시트ID\"\n"
            "2) 또는 [gcp_service_account] 블록 안에: spreadsheet_id = \"시트ID\""
        )
        return create_sample_students_df()

    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
        client = gspread.authorize(creds)

        sh = client.open_by_key(spreadsheet_id)
        ws = sh.sheet1  # 첫 번째 시트 사용
        records = ws.get_all_records()

        if not records:
            st.warning("⚠️ 구글 시트에 데이터가 없습니다.")
            return create_sample_students_df()

        df = pd.DataFrame(records)

        # 컬럼 자동 매핑
        col_num_candidates = ["Number", "번호", "NO", "No", "no", "Num"]
        col_name_candidates = ["Name", "이름"]
        col_gender_candidates = ["Gender", "성별", "gender", "sex", "Sex"]

        def find_col(cands):
            for c in cands:
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

        needed = [c for c in ["Number", "Name", "Gender"] if c in df.columns]
        if not needed:
            st.error("❌ 'Number', 'Name', 'Gender' 컬럼을 찾지 못했습니다.")
            return create_sample_students_df()

        df = df[needed]
        if "Number" in df.columns:
            df["Number"] = pd.to_numeric(df["Number"], errors="coerce").fillna(df["Number"])

        return df

    except Exception as e:
        st.error(f"❌ Google Sheets 오류: {e}")
        return create_sample_students_df()


STUDENTS_DF = load_student_data()
STUDENTS_LIST = STUDENTS_DF.to_dict("records")


# =====================================
# 3. 학생 dict → 좌석 dict
# =====================================
def student_to_seat(student: dict):
    if student is None:
        return None
    gender = str(student.get("Gender", "")).strip()
    if gender in ["F", "여", "여자"]:
        color = "#F5B7B1"  # 여
    elif gender in ["M", "남", "남자"]:
        color = "#A9CCE3"  # 남
    else:
        color = "#e5e7eb"

    label = f"{student.get('Number', '')} {student.get('Name', '')}".strip()
    return {"name": label, "color": color}


# =====================================
# 4. 좌석 배치 (Single / Paired)
# =====================================
def assign_seats(student_list, rows, bun_dan, mode):
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
            for _ in range(bun_dan):
                if pair_idx < len(pairs):
                    s1, s2 = pairs[pair_idx]
                    row_data.append(s1)
                    row_data.append(s2)
                else:
                    row_data.append(None)
                    row_data.append(None)
                pair_idx += 1
            seat_matrix.append(row_data)
        return seat_matrix

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


# =====================================
# 5. 화면 렌더링용 CSS + HTML
# =====================================
HTML_STYLE = """
<style>
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
        width: 110px;
        height: 55px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        font-size: 14px;
        padding: 4px;
        border: 2px solid #555;
        color: #1f2937;
        box-shadow: 0 2px 4px rgba(0,0,0,0.15);
    }
    .empty-desk {
        background-color: #e0e7ff;
        border-style: dashed;
        color: #9ca3af;
    }
    .front-of-class {
        font-size: 1.5em;
        font-weight: 900;
        color: #2563eb;
        padding: 8px 16px;
        border: 3px solid #2563eb;
        border-radius: 12px;
        background-color: #eff6ff;
        display: inline-block;
    }
</style>
"""


def render_chart(matrix, view_mode, bun_dan, seating_mode):
    rows = len(matrix)
    if rows == 0:
        return "<div>데이터 없음</div>"

    cols = len(matrix[0])

    # 교사용: 교탁에서 보게 → 앞줄이 아래쪽이 되도록 행 순서 뒤집어서 표시
    # 학생용: 종이에서 보게 → 앞줄이 위쪽 (그대로)
    display_matrix = matrix[::-1] if view_mode == "teacher" else matrix

    grid_style = f"grid-template-columns: repeat({cols}, auto);"
    html = f'<div class="desk-grid" style="{grid_style}">'

    is_paired = seating_mode == "Paired"

    for row in display_matrix:
        for c_idx, desk in enumerate(row):
            desk_class = "desk"
            desk_style = ""
            name = ""

            extra_margin = ""
            if is_paired:
                # C 모양: 짝(두 칸) 뒤에 분단 간격
                if c_idx % 2 == 1 and c_idx != len(row) - 1:
                    extra_margin = "margin-right: 20px;"

            if desk:
                desk_style = f"background-color: {desk['color']}; border-color: {desk['color']};"
                name = desk["name"]
            else:
                desk_class += " empty-desk"
                desk_style = "border-color: #d1d5db;"
                name = "빈 자리"

            full_style = desk_style + extra_margin
            html += f'<div class="{desk_class}" style="{full_style}">{name}</div>'

    html += "</div>"
    return html


# =====================================
# 6. PDF 생성 (짝 모드 C형, 폰트 크게)
# =====================================
def draw_seating_page(c, seating_matrix, seating_mode, view_mode, bun_dan, title_text):
    width, height = landscape(A4)

    # 제목
    c.setFont(KOREAN_FONT_NAME, 24)
    c.drawCentredString(width / 2, height - 40, title_text)

    rows = len(seating_matrix)
    cols = len(seating_matrix[0]) if rows > 0 else 0

    # 교사용: 교탁 기준으로 앞줄이 아래 → 행 순서 뒤집어 그리기
    # 학생용: 앞줄이 위 → 그대로
    matrix = seating_matrix[::-1] if view_mode == "teacher" else seating_matrix

    margin_x = 40
    margin_y = 80

    base_gap_x = 10
    gap_y = 18
    pair_gap = 20 if seating_mode == "Paired" else 0

    # 세로
    available_h = height - margin_y * 2 - 60
    cell_h = (available_h - gap_y * (rows - 1)) / rows if rows > 0 else 35

    # 가로
    if cols > 0:
        available_w = width - margin_x * 2
        if seating_mode == "Paired":
            pairs = cols // 2
            total_base_gaps = (cols - 1) * base_gap_x
            total_pair_gaps = max(0, pairs - 1) * pair_gap
            cell_w = (available_w - total_base_gaps - total_pair_gaps) / cols
        else:
            total_base_gaps = (cols - 1) * base_gap_x
            cell_w = (available_w - total_base_gaps) / cols
    else:
        cell_w = 35

    start_y = height - margin_y - cell_h - 30

    for r, row in enumerate(matrix):
        y = start_y - r * (cell_h + gap_y)
        x = margin_x

        for c_idx, seat in enumerate(row):
            # 책상 사각형
            if seat:
                c.setFillColor(HexColor(seat["color"]))
                c.setStrokeColor(HexColor(seat["color"]))
            else:
                c.setFillColor(HexColor("#e0e7ff"))
                c.setStrokeColor(HexColor("#d1d5db"))

            c.rect(x, y, cell_w, cell_h, fill=1, stroke=1)

            c.setFillColor(black)
            if seat:
                c.setFont(KOREAN_FONT_NAME, 14)  # 기존보다 +2 정도 크게
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

            x += cell_w + base_gap_x

            # 짝 모드: 짝의 오른쪽 뒤에 분단 간격
            if seating_mode == "Paired" and c_idx % 2 == 1 and c_idx != cols - 1:
                x += pair_gap

    # 교탁
    desk_w = 110
    desk_h = 45
    desk_x = width / 2 - desk_w / 2

    if view_mode == "teacher":
        # 교사용: 교탁 아래쪽
        desk_y = margin_y - desk_h
    else:
        # 학생용: 교탁 위쪽
        desk_y = height - margin_y + 10

    c.setFillColor(HexColor("#eff6ff"))
    c.setStrokeColor(HexColor("#2563eb"))
    c.rect(desk_x, desk_y, desk_w, desk_h, fill=1, stroke=1)
    c.setFont(KOREAN_FONT_NAME, 16)
    c.setFillColor(HexColor("#2563eb"))
    c.drawCentredString(desk_x + desk_w / 2, desk_y + desk_h / 2 - 4, "교탁")


def generate_pdf(seating_matrix, seating_mode, view_mode, bun_dan, title_text):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    draw_seating_page(c, seating_matrix, seating_mode, view_mode, bun_dan, title_text)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


def generate_both_pdf(seating_matrix, seating_mode, bun_dan):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    # 1페이지: 교사용
    draw_seating_page(c, seating_matrix, seating_mode, "teacher", bun_dan, "교사용 좌석 배치표")
    c.showPage()
    # 2페이지: 학생용
    draw_seating_page(c, seating_matrix, seating_mode, "student", bun_dan, "학생용 좌석 배치표")
    c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue()


# =====================================
# 7. Streamlit UI
# =====================================
st.markdown(HTML_STYLE, unsafe_allow_html=True)

st.title("🧑‍🏫 좌석 배치표 (Google Sheets 연동)")

with st.expander("현재 불러온 학생 명단 보기", expanded=False):
    st.dataframe(STUDENTS_DF)

c1, c2 = st.columns(2)
with c1:
    st.subheader("1. 좌석 형태")
    seating_mode = st.radio(
        "형태 선택",
        ("Single", "Paired"),
        index=0,
        format_func=lambda x: "혼자 앉기 (Single)" if x == "Single" else "짝으로 앉기 (Paired)",
    )
with c2:
    st.subheader("2. 교실 크기")
    bun_dan = st.number_input("분단 수", min_value=2, max_value=10, value=4, step=1)
    rows = st.number_input("줄 수 (행)", min_value=2, max_value=10, value=5, step=1)

if st.button("🎉 좌석 배치표 생성", type="primary"):
    if seating_mode == "Paired":
        seats_per_row = int(bun_dan) * 2
    else:
        seats_per_row = int(bun_dan)

    total_desks = int(rows) * seats_per_row
    num_students = len(STUDENTS_LIST)

    if total_desks < num_students:
        st.error("⚠️ 좌석이 부족해요.")
        st.warning(f"학생 {num_students}명 / 자리 {total_desks}석")
    else:
        matrix = assign_seats(STUDENTS_LIST, int(rows), int(bun_dan), seating_mode)
        st.session_state["seating_matrix"] = matrix
        st.session_state["seating_mode"] = seating_mode
        st.session_state["bun_dan"] = int(bun_dan)
        st.session_state["rows"] = int(rows)
        st.success(f"총 {num_students}명을 {int(rows)}줄, {int(bun_dan)}분단에 배치했습니다.")


# ===== 결과 + PDF 버튼 =====
if "seating_matrix" in st.session_state:
    matrix = st.session_state["seating_matrix"]
    mode_saved = st.session_state["seating_mode"]
    bun_dan_saved = st.session_state["bun_dan"]

    st.markdown("---")
    st.header("1️⃣ 교사 시야 (교탁에서 봤을 때)")
    st.markdown(
        render_chart(matrix, "teacher", bun_dan_saved, mode_saved),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="text-align:center; margin-top: 10px;"><span class="front-of-class">교탁 (Front)</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.header("2️⃣ 학생 시야 (배포용)")
    st.markdown(
        '<div style="text-align:center; margin-bottom: 10px;"><span class="front-of-class">교탁 (Front)</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        render_chart(matrix, "student", bun_dan_saved, mode_saved),
        unsafe_allow_html=True,
    )

    # PDF
    teacher_pdf = generate_pdf(matrix, mode_saved, "teacher", bun_dan_saved, "교사용 좌석 배치표")
    student_pdf = generate_pdf(matrix, mode_saved, "student", bun_dan_saved, "학생용 좌석 배치표")
    both_pdf = generate_both_pdf(matrix, mode_saved, bun_dan_saved)

    st.markdown("---")
    st.subheader("📄 PDF 다운로드")

    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "📥 교사용 PDF",
            data=teacher_pdf,
            file_name="seating_teacher.pdf",
            mime="application/pdf",
        )
    with d2:
        st.download_button(
            "📥 학생용 PDF",
            data=student_pdf,
            file_name="seating_student.pdf",
            mime="application/pdf",
        )
    with d3:
        st.download_button(
            "📥 교사+학생 한 번에",
            data=both_pdf,
            file_name="seating_both.pdf",
            mime="application/pdf",
        )

# 범례
st.markdown("---")
st.subheader("🌈 범례")
l1, l2, l3 = st.columns(3)
with l1:
    st.markdown(
        '<div class="desk" style="background-color:#F5B7B1;border-color:#F5B7B1;">여학생 (Pink)</div>',
        unsafe_allow_html=True,
    )
with l2:
    st.markdown(
        '<div class="desk" style="background-color:#A9CCE3;border-color:#A9CCE3;">남학생 (Blue)</div>',
        unsafe_allow_html=True,
    )
with l3:
    st.markdown(
        '<div class="desk empty-desk" style="border-color:#d1d5db;">빈 자리</div>',
        unsafe_allow_html=True,
    )

st.caption("이름은 '번호 이름' 형식으로 표시됩니다. (예: 1 홍길동)")
