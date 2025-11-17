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


# =========================
# 0. 한글 폰트 등록 (MaruBuri)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "fonts", "MaruBuri-Regular.otf")
KOREAN_FONT_NAME = "MaruBuri"

if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont(KOREAN_FONT_NAME, FONT_PATH))
else:
    print("⚠️ Korean font file not found:", FONT_PATH)


# =========================
# 1. 학생 데이터 (샘플)
#    → 나중에 구글 시트로 바꿔도 됨
# =========================
def load_student_data():
    data = {
        "Number": list(range(1, 25)),
        "Name": [
            "김철수", "이영희", "박지민", "최민준", "정하늘", "윤서연",
            "강도현", "한지우", "오민재", "서예진", "신현우", "유진아",
            "임태경", "장미나", "전호준", "조아라", "차승원", "허다인",
            "구범수", "나유리", "류준열", "문채원", "변요한", "송혜교"
        ],
        "Gender": [
            "M", "F", "F", "M", "M", "F",
            "M", "F", "M", "F", "M", "F",
            "M", "F", "M", "F", "M", "F",
            "M", "F", "M", "F", "M", "F",
        ],
    }
    df = pd.DataFrame(data)
    return df


STUDENTS_DF = load_student_data()
STUDENTS_LIST = STUDENTS_DF.to_dict("records")


# =========================
# 2. 헬퍼: 학생 dict → 좌석 dict
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
                    row_data.append(s1)
                    row_data.append(s2)
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
# 4. HTML / CSS 렌더링
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
    bun_dan: 분단 수 (HTML에서는 cols는 row 길이로 계산)
    seating_mode: 'Single' / 'Paired'
    """
    rows = len(matrix)
    if rows == 0:
        return "<div>데이터 없음</div>"

    cols = len(matrix[0])
    display_matrix = matrix if view_mode == "teacher" else matrix[::-1]

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
                if c_idx % 2 == 0:
                    desk_class += " paired-desk-left"
                else:
                    desk_class += " paired-desk-right"
                    # 짝의 오른쪽 자리이고, 마지막이 아니면 분단 사이 여백
                    if c_idx != len(row) - 1:
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
# 5. PDF 생성 (각 자리 간격 넉넉히)
# =========================
def generate_pdf(seating_matrix, seating_mode, view_mode, bun_dan, title_text="좌석 배치표"):
    """
    seating_matrix: 2D list (각 원소: {'name','color'} 또는 None)
    seating_mode: 'Single' / 'Paired'
    view_mode: 'teacher' / 'student'
    bun_dan: 분단 수 (짝 모드일 때 분단 간 간격 계산용)
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    # ===== 제목 =====
    c.setFont(KOREAN_FONT_NAME, 18)
    c.drawCentredString(width / 2, height - 40, title_text)

    rows = len(seating_matrix)
    cols = len(seating_matrix[0]) if rows > 0 else 0

    # 시야에 따라 행 순서 뒤집기
    matrix = seating_matrix if view_mode == "teacher" else seating_matrix[::-1]

    # 여백
    margin_x = 50
    margin_y = 80

    # 좌석 사이 간격
    seat_gap_x = 8   # 가로 간격
    seat_gap_y = 10  # 세로 간격

    # 사용 가능한 높이 계산 (윗/아랫 여백 + 교탁 공간)
    available_height = height - margin_y * 2 - 40
    if rows > 0:
        cell_h = (available_height - seat_gap_y * (rows - 1)) / rows
    else:
        cell_h = 40

    # 가로 방향 폭/간격 계산
    if seating_mode == "Paired":
        seat_cols = bun_dan * 2  # 실제 좌석 칸 수
        pair_gap = 12            # 분단 사이 간격

        if seat_cols > 0:
            total_pair_gaps = (bun_dan - 1) * pair_gap
            total_seat_gaps = (seat_cols - 1) * seat_gap_x
            available_width = width - margin_x * 2 - total_pair_gaps - total_seat_gaps
            cell_w = available_width / seat_cols
        else:
            cell_w = 40
    else:
        seat_cols = cols
        pair_gap = 0
        if seat_cols > 0:
            total_seat_gaps = (seat_cols - 1) * seat_gap_x
            available_width = width - margin_x * 2 - total_seat_gaps
            cell_w = available_width / seat_cols
        else:
            cell_w = 40

    # 좌석 시작 y (맨 윗줄)
    start_y = height - margin_y - cell_h

    # ===== 좌석 그리기 =====
    for r, row in enumerate(matrix):
        y = start_y - r * (cell_h + seat_gap_y)
        x = margin_x

        if seating_mode == "Paired":
            for c_idx, seat in enumerate(row):
                # 짝 사이 기본 간격
                if c_idx > 0:
                    x += seat_gap_x
                # 새로운 짝(분단)이 시작될 때마다 pair_gap 추가
                if c_idx > 0 and c_idx % 2 == 0:
                    x += pair_gap

                if seat:
                    c.setFillColor(HexColor(seat["color"]))
                    c.setStrokeColor(HexColor(seat["color"]))
                else:
                    c.setFillColor(HexColor("#e0e7ff"))
                    c.setStrokeColor(HexColor("#d1d5db"))

                c.rect(x, y, cell_w, cell_h, fill=1, stroke=1)

                c.setFillColor(black)
                if seat:
                    c.setFont(KOREAN_FONT_NAME, 9)
                    c.drawCentredString(
                        x + cell_w / 2,
                        y + cell_h / 2 - 4,
                        seat["name"],
                    )
                else:
                    c.setFont(KOREAN_FONT_NAME, 8)
                    c.drawCentredString(
                        x + cell_w / 2,
                        y + cell_h / 2 - 4,
                        "빈 자리",
                    )

        else:
            # 혼자 앉기 모드
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
                    c.setFont(KOREAN_FONT_NAME, 9)
                    c.drawCentredString(
                        x + cell_w / 2,
                        y + cell_h / 2 - 4,
                        seat["name"],
                    )
                else:
                    c.setFont(KOREAN_FONT_NAME, 8)
                    c.drawCentredString(
                        x + cell_w / 2,
                        y + cell_h / 2 - 4,
                        "빈 자리",
                    )

                x += cell_w

    # ===== 교탁 (가운데 배치) =====
    desk_w = 100
    desk_h = 40
    desk_x = width / 2 - desk_w / 2

    if view_mode == "teacher":
        desk_y = height - margin_y + 5   # 위쪽
    else:
        desk_y = margin_y - desk_h - 5   # 아래쪽

    c.setFillColor(HexColor("#eff6ff"))
    c.setStrokeColor(HexColor("#2563eb"))
    c.rect(desk_x, desk_y, desk_w, desk_h, fill=1, stroke=1)
    c.setFont(KOREAN_FONT_NAME, 12)
    c.setFillColor(HexColor("#2563eb"))
    c.drawCentredString(
        desk_x + desk_w / 2,
        desk_y + desk_h / 2 - 4,
        "교탁",
    )

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
st.write("행/분단 수와 좌석 형태를 입력하면 무작위 좌석 배치표를 만들고, PDF로 저장할 수 있어요.")

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
        st.success(f"총 {num_students}명을 {int(input_rows)}줄, {int(input_cols)}분단에 배치합니다.")

        seating_matrix = assign_seats(
            STUDENTS_LIST,
            rows=int(input_rows),
            bun_dan=int(input_cols),
            mode=seating_mode,
        )

        st.markdown("---")

        # 1) 교사 시야
        st.header("1️⃣ 교사 시야 (교탁에서 아이들을 바라볼 때)")
        st.markdown(
            '<div style="text-align:center;"><div class="front-of-class">교탁 (Front of Class)</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            render_chart(seating_matrix, "teacher", int(input_cols), seating_mode),
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # 2) 학생 시야
        st.header("2️⃣ 학생 시야 (학생들에게 나누어줄 때)")
        st.markdown(
            render_chart(seating_matrix, "student", int(input_cols), seating_mode),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="text-align:center; margin-top: 15px;"><div class="front-of-class">교탁 (Front of Class)</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.subheader("📄 PDF로 저장하기")

        teacher_pdf_bytes = generate_pdf(
            seating_matrix,
            seating_mode,
            view_mode="teacher",
            bun_dan=int(input_cols),
            title_text="교사용 좌석 배치표",
        )
        student_pdf_bytes = generate_pdf(
            seating_matrix,
            seating_mode,
            view_mode="student",
            bun_dan=int(input_cols),
            title_text="학생용 좌석 배치표",
        )

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "📥 교사용 PDF 다운로드",
                data=teacher_pdf_bytes,
                file_name="seating_teacher.pdf",
                mime="application/pdf",
            )
        with c2:
            st.download_button(
                "📥 학생용 PDF 다운로드 (아이들 나눠주기)",
                data=student_pdf_bytes,
                file_name="seating_student.pdf",
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
