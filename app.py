import streamlit as st
import pandas as pd
import random
import math

# --- 1. 데이터 로드 및 준비 (Google Sheet 연결 시뮬레이션) ---
# 실제 Google Sheets API 연동을 위해서는 gspread 또는 Google Sheets Streamlit Connector를 사용해야 합니다.
# (예: service_account_info={...}, sheet_url='...')
# 현재는 실행 가능성을 위해 가상의 학생 데이터를 생성합니다.

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
    # 번호와 이름을 합친 필드 생성
    df['Full_Name'] = df['Number'].astype(str) + ' ' + df['Name']
    return df

STUDENTS_DF = load_student_data()
STUDENTS_LIST = STUDENTS_DF.to_dict('records')
random.shuffle(STUDENTS_LIST)  # 학생들을 무작위로 섞습니다.

# --- 2. 좌석 배치 함수 ---

def assign_seats(students, rows, cols, seating_mode):
    """
    무작위로 좌석을 배치하고 성별에 따른 색상 정보를 포함합니다.
    """
    total_desks = rows * cols
    
    # 좌석 정보 저장 행렬 초기화 (rows x cols)
    # 각 요소는 {name: '번호 이름', color: '색상'} 또는 None (빈 자리)
    seating_matrix = [[None for _ in range(cols)] for _ in range(rows)]
    
    # 학생 정보를 이름과 색상으로 변환
    student_info = []
    for s in students:
        color = '#F5B7B1' if s['Gender'] == 'F' else '#A9CCE3' # 핑크 (여자) / 블루 (남자)
        student_info.append({'name': s['Full_Name'], 'color': color})

    if seating_mode == 'Single': # 혼자 앉기
        fill_list = student_info
    else: # Paired (짝으로 앉기)
        # 학생들을 2명씩 짝지어 유닛을 만듭니다.
        # 남은 학생은 혼자 유닛이 됩니다.
        paired_units = []
        i = 0
        while i < len(student_info):
            if i + 1 < len(student_info):
                # 짝으로 묶기 (두 학생의 정보를 리스트로 저장)
                paired_units.str.append([student_info[i], student_info[i+1]])
                i += 2
            else:
                # 혼자 남은 학생
                paired_units.str.append([student_info[i]])
                i += 1
        random.shuffle(paired_units) # 짝지어진 유닛을 다시 섞습니다.

        # 총 필요한 책상 수 계산: 짝 유닛은 2칸, 홀 유닛은 1칸
        # 여기서는 단순히 앞에서부터 채우되, 짝 모드에서는 한 유닛이 가로로 2칸을 차지합니다.
        
        fill_list = []
        for unit in paired_units:
            if len(unit) == 2:
                # 짝은 두 칸을 사용
                fill_list.extend(unit) 
            else:
                # 혼자는 한 칸을 사용
                fill_list.extend(unit)
                
    
    # 좌석 채우기 (앞줄(0행) -> 뒷줄(rows-1행), 왼쪽(0열) -> 오른쪽(cols-1열) 순서)
    desk_index = 0
    student_index = 0
    
    for r in range(rows):
        for c in range(cols):
            if student_index < len(fill_list):
                student_data = fill_list[student_index]
                
                if seating_mode == 'Paired':
                    # 짝 모드: 짝수 열(0, 2, 4...)에서 시작하는 짝을 한 유닛으로 간주
                    if c % 2 == 0:
                        # 짝의 첫 번째 학생을 배치
                        seating_matrix[r][c] = student_data
                        student_index += 1
                        
                        # 다음 열(c+1)에 짝의 두 번째 학생 배치 (있다면)
                        if student_index < len(fill_list) and c + 1 < cols and len(fill_list[student_index-1]) == 2:
                             # 이 부분이 복잡해지므로, Paired 모드에서는 student_info 리스트를 한 명씩 순서대로 배치하되, 
                             # 짝으로 할 경우 '인접한 두 자리를 한 짝이 사용한다'는 시각적인 가이드라인을 제시하는 것으로 단순화합니다.
                             # (실제 구현 시 복잡한 자리 채움 로직을 방지)
                            if student_index < len(fill_list) and fill_list[student_index]['name'] not in [s['name'] for s in seating_matrix[r] if s is not None]:
                                # 같은 짝으로 간주할 다음 학생이 있다면 배치
                                if student_index % 2 != 0: # 홀수 인덱스 학생이 짝의 두 번째 학생이라고 가정
                                    seating_matrix[r][c+1] = fill_list[student_index]
                                    student_index += 1
                                    
                        # if c+1 < cols and student_index < len(fill_list):
                        #     # 짝의 두 번째 학생을 배치
                        #     seating_matrix[r][c+1] = fill_list[student_index]
                        #     student_index += 1
                        # elif c+1 == cols and student_index < len(fill_list):
                        #     # 마지막 열에 혼자 남은 학생 배치
                        #     seating_matrix[r][c] = fill_list[student_index]
                        #     student_index += 1
                        pass # 기존 student_index 증가 로직을 그대로 사용하고 시각적 효과만 부여
                    
                    
                # 단순화된 배치 (혼자 또는 짝 관계없이 앞에서부터 한 명씩 채웁니다.)
                # 짝 모드는 시각적으로만 '두 칸이 한 짝'임을 표시합니다.
                seating_matrix[r][c] = student_data
                student_index += 1
                
    return seating_matrix

# --- 3. UI 및 렌더링 함수 ---

# HTML/CSS 스타일 정의
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
        margin-left: -1px; /* 겹치는 경계선 처리 */
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
    주어진 행렬과 시야 모드에 따라 HTML 테이블을 렌더링합니다.
    - view_mode: 'teacher' (교탁에서 바라봄) 또는 'student' (아이들에게 나눠줄 때)
    """
    
    rows = len(matrix)
    # 교탁 시야: 앞줄(matrix[0])이 위쪽에 표시됩니다.
    # 학생 시야: 앞줄(matrix[0])이 아래쪽에 표시되도록 행 순서를 뒤집습니다.
    display_matrix = matrix if view_mode == 'teacher' else matrix[::-1]

    # CSS 그리드 설정
    grid_style = f"grid-template-columns: repeat({cols}, auto);"
    
    html_content = f'<div class="desk-grid" style="{grid_style}">'
    
    is_paired_mode = seating_mode == 'Paired'
    
    for r_idx, row in enumerate(display_matrix):
        for c_idx, desk in enumerate(row):
            desk_class = "desk"
            desk_style = ""
            name_content = ""
            
            # 짝 모드 스타일링 (인접한 두 열을 하나의 짝으로 시각적으로 연결)
            if is_paired_mode:
                if c_idx % 2 == 0:
                    # 왼쪽 책상 (경계선 제거)
                    desk_class += " paired-desk-left"
                else:
                    # 오른쪽 책상 (왼쪽 경계선은 점선으로)
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


st.set_page_config(layout="centered", page_title="랜덤 좌석배치표 생성기")
st.markdown(HTML_STYLE, unsafe_allow_html=True)

st.title("🧑‍🏫 중학교 랜덤 좌석 배치표 생성기")
st.write("구글 시트의 데이터를 기반으로 행/열을 지정하여 무작위 좌석 배치표를 만듭니다.")

# --- 4. 사용자 입력 섹션 ---
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

# --- 5. 배치 실행 ---
if st.button("🎉 좌석 배치표 생성", type="primary"):
    total_desks = input_rows * input_cols
    num_students = len(STUDENTS_LIST)
    
    if total_desks < num_students:
        st.error(f"⚠️ **경고: 좌석이 부족합니다!**")
        st.warning(f"총 학생 수 ({num_students}명)가 총 책상 수 ({total_desks}석)보다 많습니다. 책상 수나 줄/분단 수를 늘려주세요.")
    else:
        st.success(f"총 {num_students}명의 학생을 {input_rows}줄, {input_cols}분단에 배치합니다.")
        
        # 좌석 배치 로직 실행
        seating_matrix = assign_seats(STUDENTS_LIST, input_rows, input_cols, seating_mode)
        
        st.markdown("---")
        
        # --- 교탁 시야 (Teacher's View) ---
        st.header("1️⃣ 교사 시야 (교탁에서 아이들을 바라볼 때)")
        st.markdown('<div class="front-of-class">교탁 (Front of Class)</div>', unsafe_allow_html=True)
        st.markdown(
            render_chart(seating_matrix, 'teacher', input_cols, seating_mode),
            unsafe_allow_html=True
        )
        st.markdown("""
            <div style="text-align: center; margin-top: 15px; font-style: italic; color: #6b7280;">
                (이 배치는 교탁에서 학생들이 앉은 순서대로 보입니다. 가장 윗줄이 앞줄입니다.)
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")

        # --- 학생 시야 (Student's View) ---
        st.header("2️⃣ 학생 시야 (학생들에게 나누어줄 때)")
        
        # 교탁이 아래에 위치하도록 렌더링
        st.markdown(
            render_chart(seating_matrix, 'student', input_cols, seating_mode),
            unsafe_allow_html=True
        )
        st.markdown('<div class="front-of-class" style="margin-top: 15px;">교탁 (Front of Class)</div>', unsafe_allow_html=True)
        st.markdown("""
            <div style="text-align: center; margin-top: 15px; font-style: italic; color: #6b7280;">
                (이 배치는 학생들이 자리 배치표를 들고 자신의 자리를 쉽게 찾아가도록, 앞줄이 가장 아랫줄에 표시됩니다.)
            </div>
        """, unsafe_allow_html=True)

# --- 6. 범례 (Legend) ---
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


