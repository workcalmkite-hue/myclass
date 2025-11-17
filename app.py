import streamlit as st
import pandas as pd
import random
import math

# --- 1. 데이터 로드 및 준비 (Google Sheet 연결 시뮬레이션) ---

def load_student_data():
    """가상의 학생 데이터를 생성합니다."""
    data = {
        'Number': list(range(1, 25)),
        'Name': ['김철수', '이영희', '박지민', '최민준', '정하늘', '윤서연', '강도현', '한지우', '오민재', '서예진',
                 '신현우', '유진아', '임태경', '장미나', '전호준', '조아라', '차승원', '허다인', '구범수', '나유리',
                 '류준열', '문채원', '변요한', '송혜교'],
        'Gender': ['M', 'F', 'F', 'M', 'M', 'F', 'M', 'F', 'M', 'F',
                   'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F',
                   'M', 'F', 'M', 'F']
    }
    df = pd.DataFrame(data)
    return df

STUDENTS_DF = load_student_data()
STUDENTS_LIST = STUDENTS_DF.to_dict('records')


# --- 2. 좌석 배치용 헬퍼: 색 + 이름 포맷 ---

def student_to_seat(student: dict):
    """학생 dict → 좌석에 쓸 dict({'name', 'color'})로 변환."""
    if student is None:
        return None
    gender = str(student.get('Gender', '')).strip()
    if gender in ['F', '여', '여자']:
        color = "#F5B7B1"  # 여학생 핑크
    elif gender in ['M', '남', '남자']:
        color = "#A9CCE3"  # 남학생 블루
    else:
        color = "#e5e7eb"  # 기타/미지정 회색

    label = f"{student.get('Number', '')} {student.get('Name', '')}".strip()
    return {
        "name": label,
        "color": color
    }


# --- 3. 좌석 배치 함수 ---

def assign_seats(student_list, rows, cols, mode):
    """
    student_list: [{Number, Name, Gender}, ...]
    rows: 줄 수
    cols: '분단 수' (짝 모드면 실제 열은 cols*2)
    mode: 'Single' 또는 'Paired'
    """
    pair_mode = (mode == "Paired")

    # 원본 훼손 방지
    students = student_list[:]
    random.shuffle(students)

    if pair_mode:
        seats_per_row = cols * 2  # 분단당 2자리
    else:
        seats_per_row = cols

    total_seats = rows * seats_per_row

    # 학생이 좌석보다 많으면 앞에서부터 자르기
    if len(students) > total_seats:
        students = students[:total_seats]

    # --- 짝 모드 ---
    if pair_mode:
        # 짝 단위로 묶기
        pairs = []
        for i in range(0, len(students), 2):
            s1 = student_to_seat(students[i])
            s2 = student_to_seat(students[i+1]) if i + 1 < len(students) else None
            pairs.append((s1, s2))

        seat_matrix = []
        pair_idx = 0

        for r in range(rows):
            row_data = []
            for c in range(cols):  # 분단 수만큼 돌면서 분단당 2자리 채우기
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

    # --- 혼자 모드 ---
    else:
        seat_matrix = []
        idx = 0
        # seat_list로 한 번 변환
        seat_students = [student_to_seat(s) for s in students]

        for r in range(rows):
            row_data = []
            for c in range(seats_per_row):
                if idx < len(seat_students):
                    row_data.append(seat_students[idx])
                else:
                    row_data.append(None)
                idx += 1
            seat_matrix.append(row_data)

        return seat_matrix


# --- 4. UI 및 렌더링 함수 ---

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

def render_chart(matrix, view_mode, cols, seating_mode):
    """
    - matrix: 2D list (각 원소는 {'name','color'} 또는 None)
    - view_mode: 'teacher' 또는 'student'
    - cols: 실제 그리드 열 개수 (짝 모드면 분단수*2)
    """
    rows = len(matrix)
    display_matrix = matrix if view_mode == 'teacher' else matrix[::-1]

    grid_style = f"grid-template-columns: repeat({cols}, auto);"

    html_content = f'<div class="desk-grid" style="{grid_style}">'
    is_paired_mode = seating_mode == 'Paired'

    for r_idx, row in enumerate(display_matrix):
        for c_idx, desk in enumerate(row):
            desk_class = "desk"
            desk_style = ""
            name_content = ""

            if is_paired_mode:
                if c_idx % 2 == 0:
                    desk_class += " paired-desk-left"
                else:
                    desk_class += " paired-desk-right"

            if desk:
                desk_style = f"background-color: {desk['color']}; border-color: {desk['color']};"
                name_content = desk['name']
            else:
                desk_class += " empty-desk"
                desk_style = "border-color: #d1d5db;"
                name_content = "빈 자리"

            html_content += f'<div class="{desk_class}" style="{desk_style}">{name_content}</div>'

    html_content += '</div>'
    return html_content


# --- 5. Streamlit UI ---

st.set_page_config(layout="centered", page_title="랜덤 좌석배치표 생성기")
st.markdown(HTML_STYLE, unsafe_allow_html=True)

st.title("🧑‍🏫 중학교 랜덤 좌석 배치표 생성기")
st.write("구글 시트의 데이터를 기반으로 행/열을 지정하여 무작위 좌석 배치표를 만듭니다.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. 좌석 형태 선택")
    seating_mode = st.radio(
        "짝으로 앉을까요, 혼자 앉을까요?",
        ('Single', 'Paired'),
        index=0,
        format_func=lambda x: '혼자 앉기 (Single)' if x == 'Single' else '짝으로 앉기 (Paired)'
    )

with col2:
    st.subheader("2. 교실 크기 (행/열) 설정")
    input_cols = st.number_input(
        "분단 수 (열, Columns):",
        min_value=2,
        max_value=10,
        value=4,
        step=1
    )
    input_rows = st.number_input(
        "줄 수 (행, Rows):",
        min_value=2,
        max_value=10,
        value=5,
        step=1
    )

if st.button("🎉 좌석 배치표 생성", type="primary"):

    # ❗ 짝 모드일 땐 실제 좌석 수는 분단*2
    if seating_mode == 'Paired':
        seats_per_row = input_cols * 2
    else:
        seats_per_row = input_cols

    total_desks = int(input_rows * seats_per_row)
    num_students = len(STUDENTS_LIST)

    if total_desks < num_students:
        st.error(f"⚠️ **좌석이 부족합니다!**")
        st.warning(f"총 학생 수 ({num_students}명)가 총 자리 수 ({total_desks}석)보다 많습니다. 줄/분단 수를 늘려주세요.")
    else:
        st.success(f"총 {num_students}명의 학생을 {input_rows}줄, {input_cols}분단에 배치합니다. (짝 모드면 한 분단에 2자리)")

        seating_matrix = assign_seats(STUDENTS_LIST, int(input_rows), int(input_cols), seating_mode)

        st.markdown("---")

        # 실제 그리드 열 개수 (짝 모드면 *2)
        display_cols = input_cols * 2 if seating_mode == 'Paired' else input_cols

        # 교사 시야
        st.header("1️⃣ 교사 시야 (교탁에서 아이들을 바라볼 때)")
        st.markdown('<div class="front-of-class">교탁 (Front of Class)</div>', unsafe_allow_html=True)
        st.markdown(
            render_chart(seating_matrix, 'teacher', display_cols, seating_mode),
            unsafe_allow_html=True
        )
        st.markdown("""
            <div style="text-align: center; margin-top: 15px; font-style: italic; color: #6b7280;">
                (이 배치는 교탁에서 학생들이 앉은 순서대로 보입니다. 가장 윗줄이 앞줄입니다.)
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # 학생 시야
        st.header("2️⃣ 학생 시야 (학생들에게 나누어줄 때)")
        st.markdown(
            render_chart(seating_matrix, 'student', display_cols, seating_mode),
            unsafe_allow_html=True
        )
        st.markdown('<div class="front-of-class" style="margin-top: 15px;">교탁 (Front of Class)</div>', unsafe_allow_html=True)
        st.markdown("""
            <div style="text-align: center; margin-top: 15px; font-style: italic; color: #6b7280;">
                (이 배치는 학생들이 자리 배치표를 들고 자신의 자리를 쉽게 찾아가도록, 앞줄이 가장 아랫줄에 표시됩니다.)
            </div>
        """, unsafe_allow_html=True)

# 범례
st.markdown("---")
st.subheader("🌈 배치 범례")
col_legend_f, col_legend_m, col_legend_p = st.columns(3)

with col_legend_f:
    st.markdown('<div class="desk" style="background-color: #F5B7B1; border-color: #F5B7B1;">여자 학생 (Pink)</div>', unsafe_allow_html=True)
with col_legend_m:
    st.markdown('<div class="desk" style="background-color: #A9CCE3; border-color: #A9CCE3;">남자 학생 (Blue)</div>', unsafe_allow_html=True)
with col_legend_p:
    st.markdown('<div class="desk empty-desk" style="border-color: #d1d5db;">빈 자리</div>', unsafe_allow_html=True)

st.caption("학생 이름은 '번호 이름' 형태로 표시됩니다. (예: 1 홍길동)")
