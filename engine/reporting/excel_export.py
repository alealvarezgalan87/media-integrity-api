"""Generate an Excel evaluation report from audit data."""

import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ── Styles ──────────────────────────────────────────────────────────────────

DARK_BG = PatternFill(start_color="1B2A4A", end_color="1B2A4A", fill_type="solid")
HEADER_BG = PatternFill(start_color="2C3E6B", end_color="2C3E6B", fill_type="solid")
DOMAIN_BG = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")
GREEN_BG = PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid")
LIGHT_GREEN_BG = PatternFill(start_color="2ECC71", end_color="2ECC71", fill_type="solid")
YELLOW_BG = PatternFill(start_color="F39C12", end_color="F39C12", fill_type="solid")
ORANGE_BG = PatternFill(start_color="E67E22", end_color="E67E22", fill_type="solid")
RED_BG = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
PASS_BG = PatternFill(start_color="D5F5E3", end_color="D5F5E3", fill_type="solid")
FAIL_BG = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")
LIGHT_GRAY_BG = PatternFill(start_color="F2F3F4", end_color="F2F3F4", fill_type="solid")
WHITE_BG = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

WHITE_FONT = Font(color="FFFFFF", bold=True, size=11)
WHITE_FONT_SM = Font(color="FFFFFF", size=10)
DARK_FONT = Font(color="1B2A4A", size=10)
DARK_FONT_BOLD = Font(color="1B2A4A", bold=True, size=10)
TITLE_FONT = Font(color="FFFFFF", bold=True, size=16)
SUBTITLE_FONT = Font(color="FFFFFF", bold=True, size=12)

SEVERITY_FONTS = {
    "critical": Font(color="FFFFFF", bold=True, size=10),
    "high": Font(color="FFFFFF", bold=True, size=10),
    "medium": Font(color="1B2A4A", bold=True, size=10),
    "low": Font(color="1B2A4A", size=10),
}
SEVERITY_FILLS = {
    "critical": RED_BG,
    "high": ORANGE_BG,
    "medium": YELLOW_BG,
    "low": LIGHT_GREEN_BG,
}

THIN_BORDER = Border(
    left=Side(style="thin", color="BDC3C7"),
    right=Side(style="thin", color="BDC3C7"),
    top=Side(style="thin", color="BDC3C7"),
    bottom=Side(style="thin", color="BDC3C7"),
)

CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT_WRAP = Alignment(horizontal="left", vertical="center", wrap_text=True)

DOMAIN_LABELS = {
    "demand_capture_integrity": "Demand Capture Integrity",
    "automation_exposure": "Automation Exposure",
    "measurement_integrity": "Measurement Integrity",
    "capital_allocation_discipline": "Capital Allocation Discipline",
    "creative_velocity": "Creative Velocity",
}

DOMAIN_WEIGHTS = {
    "demand_capture_integrity": 25,
    "automation_exposure": 20,
    "measurement_integrity": 25,
    "capital_allocation_discipline": 20,
    "creative_velocity": 10,
}

IMPL_DESCRIPTIONS = {
    "REDUCE": "Decrease total media spend until structural issues are resolved.",
    "REWEIGHT": "Total spend level may be appropriate but allocation is wrong. Shift budget.",
    "TEST": "Structure is mostly sound but specific hypotheses need validation before scaling.",
    "HOLD": "Maintain current trajectory. Structure is healthy. Focus on incremental optimization.",
}

DOMAIN_ORDER = (
    "demand_capture_integrity",
    "automation_exposure",
    "measurement_integrity",
    "capital_allocation_discipline",
    "creative_velocity",
)


def _risk_band(score: int) -> tuple[str, PatternFill]:
    if score >= 91:
        return "Excellent", GREEN_BG
    elif score >= 76:
        return "Sound", LIGHT_GREEN_BG
    elif score >= 61:
        return "Moderate", YELLOW_BG
    elif score >= 41:
        return "High Exposure", ORANGE_BG
    else:
        return "Critical Failure", RED_BG


def _apply_row_fill(ws, row: int, col_start: int, col_end: int, fill, exclude=None):
    exclude = exclude or set()
    for col in range(col_start, col_end + 1):
        if col not in exclude:
            ws.cell(row=row, column=col).fill = fill


def _apply_row_border(ws, row: int, col_start: int, col_end: int):
    for col in range(col_start, col_end + 1):
        ws.cell(row=row, column=col).border = THIN_BORDER


def _set_col_widths(ws, widths: list[int]):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _title_row(ws, row: int, text: str, col_end: int, font=TITLE_FONT, fill=DARK_BG):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=col_end)
    c = ws.cell(row=row, column=1, value=text)
    c.font = font
    c.fill = fill
    c.alignment = CENTER
    for col in range(1, col_end + 1):
        ws.cell(row=row, column=col).fill = fill


def _header_row(ws, row: int, headers: list[str], fill=HEADER_BG):
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = WHITE_FONT
        c.fill = fill
        c.alignment = CENTER
        c.border = THIN_BORDER


def generate_audit_excel(audit_data: dict) -> bytes:
    """Generate an Excel workbook from audit data and return as bytes.

    Args:
        audit_data: Dict with keys: account_name, account_id, date_range,
                    scoring, domain_scores, red_flags, execution, run_id.

    Returns:
        Excel file content as bytes.
    """
    wb = Workbook()

    account_name = audit_data.get("account_name", "Unknown")
    account_id = audit_data.get("account_id", "")
    date_range = audit_data.get("date_range", {})
    scoring = audit_data.get("scoring", {})
    domain_scores = audit_data.get("domain_scores", {})
    red_flags = audit_data.get("red_flags", [])
    run_id = audit_data.get("run_id", "")

    composite = scoring.get("composite_score", 0) or 0
    risk_band_label = scoring.get("risk_band", "")
    capital_impl = scoring.get("capital_implication", "")
    confidence = scoring.get("confidence", "")
    flags_count = scoring.get("red_flags_count", len(red_flags))

    # ═════════════════════════════════════════════════════════════════════════
    # SHEET 1: DASHBOARD
    # ═════════════════════════════════════════════════════════════════════════
    ws_dash = wb.active
    ws_dash.title = "Dashboard"
    ws_dash.sheet_properties.tabColor = "1B2A4A"
    _set_col_widths(ws_dash, [5, 35, 18, 18, 18, 18, 25])

    _title_row(ws_dash, 1, "Media Integrity Engine — Audit Evaluation", 7)

    date_str = f"{date_range.get('start', '')} to {date_range.get('end', '')}"
    _title_row(ws_dash, 2,
               f"Client: {account_name}  |  Account: {account_id}  |  Period: {date_str}",
               7, font=WHITE_FONT_SM, fill=HEADER_BG)

    row = 4
    _title_row(ws_dash, row, "DOMAIN SCORES", 7, font=SUBTITLE_FONT, fill=DOMAIN_BG)
    row += 1

    _header_row(ws_dash, row, ["#", "Domain", "Score", "Risk Band", "Findings", "Weight", "Weighted"])
    row += 1

    idx = 0
    for key in DOMAIN_ORDER:
        idx += 1
        d = domain_scores.get(key, {})
        score_val = d.get("value", 0) or 0
        weight = DOMAIN_WEIGHTS.get(key, 0)
        label = DOMAIN_LABELS.get(key, key)
        band_name, band_fill = _risk_band(score_val)
        findings = d.get("key_findings", [])
        findings_str = "; ".join(findings) if findings else "—"
        weighted = round(score_val * weight / 100, 1)

        ws_dash.cell(row=row, column=1, value=idx).font = DARK_FONT_BOLD
        ws_dash.cell(row=row, column=1).alignment = CENTER
        ws_dash.cell(row=row, column=2, value=label).font = DARK_FONT_BOLD
        ws_dash.cell(row=row, column=2).alignment = LEFT_WRAP

        sc = ws_dash.cell(row=row, column=3, value=score_val)
        sc.font = Font(color="FFFFFF", bold=True, size=14)
        sc.fill = band_fill
        sc.alignment = CENTER

        ws_dash.cell(row=row, column=4, value=band_name).font = DARK_FONT_BOLD
        ws_dash.cell(row=row, column=4).alignment = CENTER

        ws_dash.cell(row=row, column=5, value=findings_str).font = DARK_FONT
        ws_dash.cell(row=row, column=5).alignment = LEFT_WRAP

        ws_dash.cell(row=row, column=6, value=f"{weight}%").font = DARK_FONT
        ws_dash.cell(row=row, column=6).alignment = CENTER

        ws_dash.cell(row=row, column=7, value=weighted).font = DARK_FONT_BOLD
        ws_dash.cell(row=row, column=7).alignment = CENTER

        alt_fill = LIGHT_GRAY_BG if idx % 2 == 0 else WHITE_BG
        _apply_row_fill(ws_dash, row, 1, 7, alt_fill, exclude={3})
        _apply_row_border(ws_dash, row, 1, 7)
        ws_dash.row_dimensions[row].height = 40
        row += 1

    # Composite Score
    row += 1
    _title_row(ws_dash, row, "COMPOSITE INTEGRITY SCORE", 7, font=SUBTITLE_FONT, fill=DOMAIN_BG)
    row += 1

    band_name, band_fill = _risk_band(composite)

    ws_dash.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ws_dash.cell(row=row, column=1, value="Composite Score").font = DARK_FONT_BOLD
    ws_dash.cell(row=row, column=1).alignment = Alignment(horizontal="right", vertical="center")
    sc = ws_dash.cell(row=row, column=3, value=composite)
    sc.font = Font(color="FFFFFF", bold=True, size=18)
    sc.fill = band_fill
    sc.alignment = CENTER
    ws_dash.cell(row=row, column=4, value=band_name).font = DARK_FONT_BOLD
    ws_dash.cell(row=row, column=4).alignment = CENTER
    ws_dash.cell(row=row, column=5, value=f"Confidence: {confidence}").font = DARK_FONT
    ws_dash.cell(row=row, column=5).alignment = CENTER
    _apply_row_border(ws_dash, row, 1, 7)
    row += 1

    # Capital Implication
    ws_dash.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ws_dash.cell(row=row, column=1, value="Capital Implication").font = DARK_FONT_BOLD
    ws_dash.cell(row=row, column=1).alignment = Alignment(horizontal="right", vertical="center")
    ci = ws_dash.cell(row=row, column=3, value=capital_impl)
    ci.font = Font(color="FFFFFF", bold=True, size=14)
    ci.alignment = CENTER
    impl_fills = {"REDUCE": RED_BG, "REWEIGHT": ORANGE_BG, "TEST": YELLOW_BG, "HOLD": GREEN_BG}
    ci.fill = impl_fills.get(capital_impl, YELLOW_BG)
    ws_dash.merge_cells(start_row=row, start_column=4, end_row=row, end_column=7)
    ws_dash.cell(row=row, column=4, value=IMPL_DESCRIPTIONS.get(capital_impl, "")).font = DARK_FONT
    ws_dash.cell(row=row, column=4).alignment = LEFT_WRAP
    _apply_row_border(ws_dash, row, 1, 7)
    row += 1

    # Red Flags Summary
    row += 1
    _title_row(ws_dash, row, "RED FLAGS SUMMARY", 7, font=SUBTITLE_FONT, fill=DOMAIN_BG)
    row += 1

    _header_row(ws_dash, row, ["", "Total Rules", "Triggered", "Passed", "Critical", "High", "Medium"])
    row += 1

    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in red_flags:
        sev = f.get("severity", "medium").lower()
        if sev in sev_counts:
            sev_counts[sev] += 1

    total_rules = scoring.get("total_rules_evaluated", 15)
    passed = total_rules - flags_count

    vals = ["", total_rules, flags_count, passed,
            sev_counts["critical"], sev_counts["high"], sev_counts["medium"]]
    for col, v in enumerate(vals, 1):
        c = ws_dash.cell(row=row, column=col, value=v)
        c.font = DARK_FONT_BOLD
        c.alignment = CENTER
        c.border = THIN_BORDER

    # ═════════════════════════════════════════════════════════════════════════
    # SHEET 2: RED FLAGS DETAIL
    # ═════════════════════════════════════════════════════════════════════════
    ws_flags = wb.create_sheet("Red Flags")
    ws_flags.sheet_properties.tabColor = "E74C3C"
    _set_col_widths(ws_flags, [10, 12, 30, 14, 55, 55])

    _title_row(ws_flags, 1, f"Red Flags — {account_name}", 6)
    _title_row(ws_flags, 2,
               f"{flags_count} red flag(s) triggered  |  Run: {run_id[:8] if run_id else ''}",
               6, font=WHITE_FONT_SM, fill=HEADER_BG)

    row = 4
    _header_row(ws_flags, row, ["Rule ID", "Severity", "Title", "Domain", "Description", "Recommendation"])
    row += 1

    if not red_flags:
        ws_flags.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        ws_flags.cell(row=row, column=1, value="No red flags detected.").font = DARK_FONT
        ws_flags.cell(row=row, column=1).alignment = CENTER
    else:
        current_domain = None
        for f in red_flags:
            domain = f.get("domain", "")
            domain_label = DOMAIN_LABELS.get(domain, domain)

            if domain != current_domain:
                current_domain = domain
                ws_flags.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
                c = ws_flags.cell(row=row, column=1, value=f"  {domain_label}")
                c.font = WHITE_FONT
                c.fill = DOMAIN_BG
                c.alignment = Alignment(horizontal="left", vertical="center")
                for col in range(1, 7):
                    ws_flags.cell(row=row, column=col).fill = DOMAIN_BG
                row += 1

            severity = f.get("severity", "medium").lower()

            ws_flags.cell(row=row, column=1, value=f.get("id", f.get("rule_id_raw", ""))).font = DARK_FONT_BOLD
            ws_flags.cell(row=row, column=1).alignment = CENTER

            sev_cell = ws_flags.cell(row=row, column=2, value=severity.upper())
            sev_cell.font = SEVERITY_FONTS.get(severity, DARK_FONT_BOLD)
            sev_cell.fill = SEVERITY_FILLS.get(severity, YELLOW_BG)
            sev_cell.alignment = CENTER

            ws_flags.cell(row=row, column=3, value=f.get("title", "")).font = DARK_FONT_BOLD
            ws_flags.cell(row=row, column=3).alignment = LEFT_WRAP

            ws_flags.cell(row=row, column=4, value=domain_label).font = DARK_FONT
            ws_flags.cell(row=row, column=4).alignment = LEFT_WRAP

            ws_flags.cell(row=row, column=5, value=f.get("description", "")).font = DARK_FONT
            ws_flags.cell(row=row, column=5).alignment = LEFT_WRAP

            ws_flags.cell(row=row, column=6, value=f.get("recommendation", "")).font = DARK_FONT
            ws_flags.cell(row=row, column=6).alignment = LEFT_WRAP

            _apply_row_fill(ws_flags, row, 1, 6, FAIL_BG, exclude={2})
            _apply_row_border(ws_flags, row, 1, 6)
            ws_flags.row_dimensions[row].height = 50
            row += 1

    # ═════════════════════════════════════════════════════════════════════════
    # SHEET 3: DOMAIN BREAKDOWN
    # ═════════════════════════════════════════════════════════════════════════
    ws_domains = wb.create_sheet("Domain Breakdown")
    ws_domains.sheet_properties.tabColor = "2C3E6B"
    _set_col_widths(ws_domains, [30, 15, 15, 15, 60])

    _title_row(ws_domains, 1, f"Domain Score Breakdown — {account_name}", 5)

    row = 3
    for key in DOMAIN_ORDER:
        d = domain_scores.get(key, {})
        label = DOMAIN_LABELS.get(key, key)
        score_val = d.get("value", 0) or 0
        band_name, band_fill = _risk_band(score_val)
        sub_scores = d.get("sub_scores", {})
        completeness = d.get("data_completeness", 0)

        _title_row(ws_domains, row, f"{label}  —  {score_val}/100  ({band_name})", 5,
                   font=SUBTITLE_FONT, fill=DOMAIN_BG)
        row += 1

        if sub_scores:
            _header_row(ws_domains, row, ["Sub-metric", "Value", "", "", ""])
            row += 1
            for sk, sv in sub_scores.items():
                pretty_key = sk.replace("_", " ").title()
                ws_domains.cell(row=row, column=1, value=pretty_key).font = DARK_FONT
                ws_domains.cell(row=row, column=1).alignment = LEFT_WRAP

                if isinstance(sv, float) and sv <= 1.0:
                    ws_domains.cell(row=row, column=2, value=f"{sv:.1%}").font = DARK_FONT_BOLD
                else:
                    ws_domains.cell(row=row, column=2, value=str(sv)).font = DARK_FONT_BOLD
                ws_domains.cell(row=row, column=2).alignment = CENTER
                _apply_row_border(ws_domains, row, 1, 2)
                row += 1

        findings = d.get("key_findings", [])
        if findings:
            _header_row(ws_domains, row, ["Key Findings", "", "", "", ""])
            row += 1
            for finding in findings:
                ws_domains.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
                ws_domains.cell(row=row, column=1, value=f"• {finding}").font = DARK_FONT
                ws_domains.cell(row=row, column=1).alignment = LEFT_WRAP
                ws_domains.row_dimensions[row].height = 30
                row += 1

        ws_domains.cell(row=row, column=1, value="Data Completeness").font = DARK_FONT
        if isinstance(completeness, (int, float)):
            ws_domains.cell(row=row, column=2, value=f"{completeness:.0%}").font = DARK_FONT_BOLD
        else:
            ws_domains.cell(row=row, column=2, value=str(completeness)).font = DARK_FONT_BOLD
        ws_domains.cell(row=row, column=2).alignment = CENTER
        row += 2

    # ═════════════════════════════════════════════════════════════════════════
    # SHEET 4: EXECUTION LOG
    # ═════════════════════════════════════════════════════════════════════════
    ws_exec = wb.create_sheet("Execution")
    ws_exec.sheet_properties.tabColor = "27AE60"
    _set_col_widths(ws_exec, [25, 40])

    _title_row(ws_exec, 1, "Execution Details", 2)

    execution = audit_data.get("execution", {})
    row = 3
    meta_items = [
        ("Run ID", run_id),
        ("Account Name", account_name),
        ("Account ID", account_id),
        ("Date Range", date_str),
        ("Composite Score", composite),
        ("Risk Band", risk_band_label),
        ("Capital Implication", capital_impl),
        ("Confidence", confidence),
        ("Red Flags Count", flags_count),
        ("Duration (s)", execution.get("duration_seconds", "")),
        ("Source", execution.get("source", "")),
        ("Timestamp", execution.get("timestamp", "")),
    ]

    for label, value in meta_items:
        ws_exec.cell(row=row, column=1, value=label).font = DARK_FONT_BOLD
        ws_exec.cell(row=row, column=1).alignment = LEFT_WRAP
        ws_exec.cell(row=row, column=2, value=str(value) if value else "—").font = DARK_FONT
        ws_exec.cell(row=row, column=2).alignment = LEFT_WRAP
        _apply_row_border(ws_exec, row, 1, 2)
        row += 1

    # ═════════════════════════════════════════════════════════════════════════
    # SAVE TO BYTES
    # ═════════════════════════════════════════════════════════════════════════
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
