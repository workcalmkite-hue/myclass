def draw_pdf_page(c, matrix, seating_mode, view_mode, bun_dan, title):
    width, height = landscape(A4)

    margin_y = 80
    gap_x = 10
    gap_y = 18
    pair_gap = 22 if seating_mode == "Paired" else 0

    # ---------- 1) 행 순서 (교사용/학생용) ----------
    if view_mode == "teacher":
        # 교탁 기준: 앞줄이 아래에 오도록 뒤집어서 보여줌
        matrix_to_draw = matrix[::-1]
    else:
        # 학생용: 앞줄이 위에 보이도록 그대로
        matrix_to_draw = matrix

    rows = len(matrix_to_draw)
    cols = len(matrix_to_draw[0])

    # ---------- 2) 제목 위치 ----------
    if view_mode == "teacher":
        # 교사용: 위쪽에 제목
        title_y = height - 40
    else:
        # 학생용: 아래쪽에 제목
        title_y = margin_y / 2

    c.setFont(KOREAN_FONT, 26)
    c.drawCentredString(width / 2, title_y, title)

    # ---------- 3) 좌석 영역 계산 (가운데 정렬) ----------
    available_h = height - margin_y * 2 - 80
    cell_h = (available_h - gap_y * (rows - 1)) / rows if rows > 0 else 40

    total_base_gaps = (cols - 1) * gap_x
    total_pair_gaps = (bun_dan - 1) * pair_gap if seating_mode == "Paired" else 0

    available_w = width - 80  # 양쪽 대략 40pt 여백
    cell_w = (available_w - total_base_gaps - total_pair_gaps) / cols if cols > 0 else 40

    total_width = cols * cell_w + total_base_gaps + total_pair_gaps
    start_x = (width - total_width) / 2  # 가로 중앙

    # 세로 시작점: 위에서부터 아래로 줄 내려감
    start_y = height - margin_y - cell_h

    # ---------- 4) 좌석 사각형/이름 그리기 ----------
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

    # ---------- 5) 교탁 위치 ----------
    desk_w = 130
    desk_h = 48
    desk_x = width / 2 - desk_w / 2

    if view_mode == "teacher":
        # 교사용: 교탁은 맨 아래 중앙
        desk_y = margin_y - desk_h
    else:
        # 학생용: 교탁은 맨 위 중앙 (앞쪽)
        desk_y = height - margin_y + 10

    c.setFillColor(HexColor("#eff6ff"))
    c.setStrokeColor(HexColor("#2563eb"))
    c.rect(desk_x, desk_y, desk_w, desk_h, fill=1, stroke=1)
    c.setFont(KOREAN_FONT, 18)
    c.setFillColor(HexColor("#2563eb"))
    c.drawCentredString(desk_x + desk_w / 2, desk_y + desk_h / 2 - 4, "교탁")
