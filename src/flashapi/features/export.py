"""Export functionality — CSV (built-in), XLSX and PDF (optional deps)."""

from __future__ import annotations

import csv
import io
from typing import Any


def export_csv(items: list[dict[str, Any]], fields: list[str]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow({k: item.get(k, "") for k in fields})
    return output.getvalue().encode("utf-8")


def export_xlsx(items: list[dict[str, Any]], fields: list[str]) -> bytes:
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl is required for XLSX export: pip install openpyxl")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(fields)
    for item in items:
        ws.append([item.get(f, "") for f in fields])

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def export_pdf(items: list[dict[str, Any]], fields: list[str]) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
        from reportlab.lib import colors
    except ImportError:
        raise ImportError("reportlab is required for PDF export: pip install reportlab")

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    table_data = [fields]
    for item in items:
        table_data.append([str(item.get(f, "")) for f in fields])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    doc.build([table])
    return output.getvalue()


EXPORTERS = {
    "csv": export_csv,
    "xlsx": export_xlsx,
    "pdf": export_pdf,
}

CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
