"""POST /api/export — export edited questions to JSON / XLSX / CSV."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.export.exporters import export_csv, export_json, export_xlsx
from app.schemas.quiz import ExportRequest

router = APIRouter(tags=["export"])


@router.post("/export")
async def export_questions(req: ExportRequest):
    """Accept the (possibly user-edited) questions and return a download."""
    fmt = req.format.lower()

    if fmt == "json":
        data = export_json(req.questions)
        return Response(
            content=data,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=quiz.json"},
        )

    if fmt == "xlsx":
        data = export_xlsx(req.questions)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=quiz.xlsx"},
        )

    if fmt == "csv":
        data = export_csv(req.questions)
        return Response(
            content=data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=quiz.csv"},
        )

    raise HTTPException(status_code=400, detail=f"Unknown format: {fmt}")
