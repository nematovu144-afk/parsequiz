"""Serialise Question lists into downloadable formats."""

from __future__ import annotations

import csv
import io
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.schemas.quiz import Question


def export_json(questions: list[Question]) -> bytes:
    """Clean JSON array (no internal flags)."""
    payload = [
        {
            "id": str(q.id),
            "question": q.question,
            "options": q.options,
            "correct_option_index": q.correct_option_index,
            "explanation": q.explanation,
        }
        for q in questions
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def export_xlsx(questions: list[Question]) -> bytes:
    """Styled Excel workbook with one row per question."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Quiz"

    # Header row
    headers = ["#", "Question", "Option A", "Option B", "Option C", "Option D",
               "Correct", "Explanation"]
    header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Data rows
    for i, q in enumerate(questions, 2):
        ws.cell(row=i, column=1, value=i - 1)
        ws.cell(row=i, column=2, value=q.question)
        for j, opt in enumerate(q.options[:4]):
            ws.cell(row=i, column=3 + j, value=opt)
        if q.correct_option_index is not None and q.correct_option_index < len(q.options):
            letter = chr(65 + q.correct_option_index)  # A, B, C, D
            ws.cell(row=i, column=7, value=letter)
        ws.cell(row=i, column=8, value=q.explanation or "")

    # Column widths
    ws.column_dimensions["B"].width = 50
    for col_letter in "CDEF":
        ws.column_dimensions[col_letter].width = 30

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_csv(questions: list[Question]) -> bytes:
    """UTF-8 CSV with BOM for Excel compatibility."""
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM
    writer = csv.writer(buf)
    writer.writerow(["#", "Question", "Option A", "Option B", "Option C",
                      "Option D", "Correct", "Explanation"])

    for i, q in enumerate(questions, 1):
        opts = q.options + [""] * (4 - len(q.options))  # pad to 4
        correct = ""
        if q.correct_option_index is not None and q.correct_option_index < len(q.options):
            correct = chr(65 + q.correct_option_index)
        writer.writerow([i, q.question, *opts[:4], correct, q.explanation or ""])

    return buf.getvalue().encode("utf-8")
