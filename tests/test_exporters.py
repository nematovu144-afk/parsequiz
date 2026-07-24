"""Unit tests for JSON/XLSX/CSV export serializers."""

import csv
import io
import json

from openpyxl import load_workbook

from app.export.exporters import export_csv, export_json, export_xlsx
from app.schemas.quiz import Question

QUESTIONS = [
    Question(
        question="Capital of France?",
        options=["London", "Paris", "Berlin"],
        correct_option_index=1,
        explanation="Paris has been the capital since 987.",
    ),
]


def test_export_json_roundtrip():
    data = json.loads(export_json(QUESTIONS))
    assert len(data) == 1
    assert data[0]["question"] == "Capital of France?"
    assert data[0]["options"] == ["London", "Paris", "Berlin"]
    assert data[0]["correct_option_index"] == 1
    # internal validation flags must not leak into the export
    assert "flags" not in data[0]


def test_export_csv_has_header_and_correct_letter():
    text = export_csv(QUESTIONS).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][:2] == ["#", "Question"]
    assert rows[1][1] == "Capital of France?"
    assert rows[1][2:5] == ["London", "Paris", "Berlin"]
    assert rows[1][6] == "B"  # correct_option_index=1 -> letter B


def test_export_xlsx_has_correct_letter_and_headers():
    wb = load_workbook(io.BytesIO(export_xlsx(QUESTIONS)))
    ws = wb.active
    assert ws.cell(row=1, column=2).value == "Question"
    assert ws.cell(row=2, column=2).value == "Capital of France?"
    assert ws.cell(row=2, column=7).value == "B"


def test_export_empty_list_does_not_crash():
    assert json.loads(export_json([])) == []
    export_csv([])
    export_xlsx([])
