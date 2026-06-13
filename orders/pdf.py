# orders/pdf.py

import os
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, Image,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from django.conf import settings as django_settings

try:
    from num2words import num2words
except ImportError:
    num2words = None

def generate_invoice_pdf(order, transaction, profile, invoice_type="final"):
    """
    Build a branded A4 TAX INVOICE or ADVANCE RECEIPT PDF using ReportLab.
    Matches reference format: logo, GST table with CGST/SGST breakdown.
    """
    # ── Colours ────────────────────────────────────────────────────────
    C_DARK   = colors.HexColor("#1C0A0C")
    C_BURNT  = colors.HexColor("#341417")
    C_STROKE = colors.HexColor("#EDE8E3")
    C_MUTED  = colors.HexColor("#8A7F7A")
    C_WARM   = colors.HexColor("#F3EDE6")
    C_GREEN  = colors.HexColor("#2E9E55")
    C_WHITE  = colors.white
    C_SUB    = colors.HexColor("#E5C5C8")
    C_LIGHT  = colors.HexColor("#F9F5F2")

    # ── Helpers ────────────────────────────────────────────────────────
    def humanise(s):
        return s.replace("_", " ").title() if s else "—"

    def fmt_date(dt):
        if not dt:
            return "—"
        try:
            from django.utils import timezone
            return timezone.localtime(dt).strftime("%d/%m/%Y")
        except Exception:
            return str(dt)

    def ps(name, **kwargs):
        return ParagraphStyle(name, **kwargs)

    # ── GST Calculations ───────────────────────────────────────────────
    gst_pct      = Decimal(str(order.gst_percentage)) if order.gst_percentage else Decimal("5")
    half_gst     = gst_pct / 2

    if invoice_type == "advance":
        total_round  = Decimal(str(order.advance_amount)) if order.advance_amount else Decimal("0")
        subtotal     = (total_round / (Decimal("1") + gst_pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cgst_amt     = (subtotal * half_gst / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst_amt     = (total_round - subtotal - cgst_amt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_exact  = total_round
        rounding_adj = Decimal("0")
    else:
        qty          = Decimal(str(order.total_quantity))
        unit_price   = Decimal(str(order.unit_price))   if order.unit_price   else Decimal("0")
        subtotal     = (unit_price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cgst_amt     = (subtotal * half_gst / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst_amt     = (subtotal * half_gst / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_exact  = subtotal + cgst_amt + sgst_amt
        total_round  = total_exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        rounding_adj = total_round - total_exact

    # ── Document setup ─────────────────────────────────────────────────
    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm,  bottomMargin=15*mm,
    )
    W     = doc.width
    story = []

    s_body  = ps("body",  fontSize=9,  fontName="Helvetica",      textColor=C_DARK,  leading=13)
    s_muted = ps("muted", fontSize=8,  fontName="Helvetica",      textColor=C_MUTED, leading=12)
    s_bold  = ps("bold",  fontSize=9,  fontName="Helvetica-Bold", textColor=C_DARK,  leading=13)
    s_right = ps("right", fontSize=9,  fontName="Helvetica",      textColor=C_DARK,  alignment=TA_RIGHT)
    s_rbold = ps("rbold", fontSize=9,  fontName="Helvetica-Bold", textColor=C_DARK,  alignment=TA_RIGHT)

    def th(align=TA_LEFT):
        return ps(f"th{align}", fontSize=8, fontName="Helvetica-Bold",
                  textColor=C_WHITE, alignment=align)

    # ══════════════════════════════════════════════════════════════════
    #  HEADER — Logo left, TAX INVOICE right
    # ══════════════════════════════════════════════════════════════════
    logo_path = os.path.join(django_settings.BASE_DIR, "static", "images", "logo.png")
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=28*mm, height=28*mm, kind="proportional")
        logo_cell = logo_img
    else:
        logo_cell = Paragraph("<b>HUEZO</b>",
                              ps("fb", fontSize=20, fontName="Helvetica-Bold", textColor=C_BURNT))

    title_text = "ADVANCE RECEIPT" if invoice_type == "advance" else "TAX INVOICE"
    hdr = Table([[
        logo_cell,
        Table([[
            Paragraph(f"<b>{title_text}</b>",
                      ps("ti", fontSize=20, fontName="Helvetica-Bold",
                         textColor=C_BURNT, alignment=TA_RIGHT)),
        ]], colWidths=[W * 0.6]),
    ]], colWidths=[W * 0.4, W * 0.6])
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width="100%", thickness=2, color=C_BURNT))
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  COMPANY INFO + INVOICE META (two columns)
    # ══════════════════════════════════════════════════════════════════
    paid_at  = fmt_date(transaction.paid_at) if transaction else "—"
    pay_ref  = (transaction.payment_reference or "—") if transaction else "—"

    company_lines = [
        Paragraph("<b>HUEZO Fashion Manufacturing</b>",
                  ps("cn", fontSize=10, fontName="Helvetica-Bold", textColor=C_DARK)),
        Paragraph("huezo.in  |  support@huezo.in",  s_muted),
    ]

    meta_rows = [
        ("#",             order.order_number),
        ("Invoice Date",  paid_at),
        ("Terms",         "Due on Receipt"),
        ("Due Date",      paid_at),
        ("Place Of Supply", "Tamil Nadu (33)"),
    ]
    meta_tbl = Table(
        [[Paragraph(k, s_muted), Paragraph(v, s_bold)] for k, v in meta_rows],
        colWidths=[30*mm, W/2 - 34*mm],
    )
    meta_tbl.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
    ]))

    info_col = Table([[p] for p in company_lines], colWidths=[W/2 - 4*mm])
    top_row  = Table([[info_col, meta_tbl]], colWidths=[W/2, W/2])
    top_row.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(top_row)
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  BILL TO / SHIP TO
    # ══════════════════════════════════════════════════════════════════
    brand_name   = getattr(profile, "brand_name",   None) or ""
    contact_name = getattr(profile, "contact_name", None) or ""
    phone        = getattr(profile, "phone",        None) or ""
    address      = ""
    if profile:
        try:
            fa = profile.full_address
            address = fa() if callable(fa) else (fa or "")
        except Exception:
            pass

    def addr_block(title):
        rows = [[Paragraph(f"<b>{title}</b>",
                           ps(title, fontSize=9, fontName="Helvetica-Bold", textColor=C_WHITE))]]
        if brand_name:
            rows.append([Paragraph(f"<b>{brand_name}</b>", s_bold)])
        if contact_name:
            rows.append([Paragraph(contact_name, s_body)])
        if address:
            rows.append([Paragraph(address, s_muted)])
        if phone:
            rows.append([Paragraph(phone, s_body)])
        tbl = Table(rows, colWidths=[W/2 - 4*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  C_BURNT),
            ("TOPPADDING",    (0, 0), (-1, 0),  6),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 1), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_STROKE),
        ]))
        return tbl

    addr_row = Table([[addr_block("Bill To"), addr_block("Ship To")]],
                     colWidths=[W/2, W/2])
    addr_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",  (1, 0), (1, -1),  4),
    ]))
    story.append(addr_row)
    story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  ITEMS TABLE  with HSN / Qty / Rate / CGST / SGST / Amount
    # ══════════════════════════════════════════════════════════════════
    unit = "meters" if order.order_type == "fabrics" else "pcs"

    # Build description string
    desc_suffix = " (Advance Payment)" if invoice_type == "advance" else ""
    desc_parts = [humanise(order.order_type) + desc_suffix]
    if order.garment_type:
        desc_parts.append(order.garment_type)
    if order.style_name:
        desc_parts.append(order.style_name)
    if order.white_label_catalogue:
        desc_parts.append(f"Prototype: {order.white_label_catalogue.prototype_code}")
    if order.fabric_catalogue:
        desc_parts.append(f"Fabric: {order.fabric_catalogue.fabric_name}")
    if order.size_breakdown:
        try:
            import json
            sizes = order.size_breakdown
            if isinstance(sizes, str):
                sizes = json.loads(sizes)
            for sb in sizes:
                desc_parts.append(f"as per dc: {sb.get('size','?')} - {sb.get('quantity','?')} {unit}")
        except Exception:
            pass
    desc_str = "\n".join(desc_parts)

    hsn = order.hsn_code or "—"

    # Column widths: #, Description, HSN, Qty, Rate, CGST%, CGSTAmt, SGST%, SGSTAmt, Amount
    cw = [8*mm, W-148*mm, 18*mm, 16*mm, 20*mm, 12*mm, 20*mm, 12*mm, 20*mm, 22*mm]

    header_row = [
        Paragraph("<b>#</b>",           th()),
        Paragraph("<b>Item &amp; Description</b>", th()),
        Paragraph("<b>HSN/SAC</b>",     th(TA_CENTER)),
        Paragraph("<b>Qty</b>",         th(TA_RIGHT)),
        Paragraph("<b>Rate</b>",        th(TA_RIGHT)),
        Paragraph(f"<b>CGST%</b>",      th(TA_CENTER)),
        Paragraph("<b>CGST Amt</b>",    th(TA_RIGHT)),
        Paragraph(f"<b>SGST%</b>",      th(TA_CENTER)),
        Paragraph("<b>SGST Amt</b>",    th(TA_RIGHT)),
        Paragraph("<b>Amount</b>",      th(TA_RIGHT)),
    ]

    if invoice_type == "advance":
        qty_val = Decimal("1.00")
        rate_val = subtotal
    else:
        qty_val = Decimal(str(order.total_quantity))
        rate_val = Decimal(str(order.unit_price)) if order.unit_price else Decimal("0")

    data_row = [
        Paragraph("1",                                   s_body),
        Paragraph(desc_str.replace("\n", "<br/>"),       s_muted),
        Paragraph(hsn,                                   ps("hc", fontSize=8, fontName="Helvetica", textColor=C_DARK, alignment=TA_CENTER)),
        Paragraph(f"{qty_val:.2f}",                      s_right),
        Paragraph(f"{rate_val:,.2f}",                    s_right),
        Paragraph(f"{half_gst:.1f}%",                    ps("cp", fontSize=8, fontName="Helvetica", textColor=C_DARK, alignment=TA_CENTER)),
        Paragraph(f"{cgst_amt:,.2f}",                    s_right),
        Paragraph(f"{half_gst:.1f}%",                    ps("sp", fontSize=8, fontName="Helvetica", textColor=C_DARK, alignment=TA_CENTER)),
        Paragraph(f"{sgst_amt:,.2f}",                    s_right),
        Paragraph(f"{subtotal:,.2f}",                    s_rbold),
    ]

    items_tbl = Table([header_row, data_row], colWidths=cw, repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_BURNT),
        ("TOPPADDING",    (0, 0), (-1, 0),  7),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("BACKGROUND",    (0, 1), (-1, -1), C_WARM),
        ("TOPPADDING",    (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, C_STROKE),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_STROKE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, C_STROKE),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 3*mm))

    # ══════════════════════════════════════════════════════════════════
    #  TOTALS — Items count left, breakdown right
    # ══════════════════════════════════════════════════════════════════
    items_count = Paragraph(
        f"Items in Total {qty_val:.2f}",
        ps("ic", fontSize=9, fontName="Helvetica-Bold", textColor=C_DARK),
    )

    if invoice_type == "advance":
        total_rows = [
            ("Sub Total",                      f"{subtotal:,.2f}",      False),
            (f"CGST ({half_gst}%)",            f"{cgst_amt:,.2f}",     False),
            (f"SGST ({half_gst}%)",            f"{sgst_amt:,.2f}",     False),
            ("Total (Advance Paid)",            f"Rs.{total_round:,.2f}", True),
            ("Balance Due",                     "Rs.0.00", True),
        ]
    else:
        advance_paid = Decimal(str(order.advance_amount)) if order.advance_amount else Decimal("0")
        final_balance_paid = total_round - advance_paid
        total_rows = [
            ("Sub Total",                      f"{subtotal:,.2f}",      False),
            (f"CGST ({half_gst}%)",            f"{cgst_amt:,.2f}",     False),
            (f"SGST ({half_gst}%)",            f"{sgst_amt:,.2f}",     False),
            ("Rounding",                        f"{rounding_adj:+.2f}", False),
            ("Total Order Amount",              f"Rs.{total_round:,.2f}", True),
            ("Less: Advance Paid",              f"Rs.{advance_paid:,.2f}", False),
            ("Final Balance Paid",              f"Rs.{final_balance_paid:,.2f}", True),
            ("Balance Due",                     "Rs.0.00", True),
        ]

    tr_data = []
    for label, value, bold in total_rows:
        fn = "Helvetica-Bold" if bold else "Helvetica"
        fs = 10 if bold else 9
        tr_data.append([
            Paragraph(label, ps(f"tl{label}", fontSize=fs, fontName=fn,
                                textColor=C_DARK, alignment=TA_RIGHT)),
            Paragraph(value, ps(f"tv{label}", fontSize=fs, fontName=fn,
                                textColor=C_GREEN if bold else C_DARK, alignment=TA_RIGHT)),
        ])

    totals_tbl = Table(tr_data, colWidths=[40*mm, 32*mm])
    
    t_style = [
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for idx, (label, _, bold) in enumerate(total_rows):
        if bold:
            t_style.append(("LINEABOVE", (0, idx), (-1, idx), 1 if label.startswith("Total") or label.startswith("Final") else 0.5, C_STROKE))
        elif label.startswith("Less"):
            t_style.append(("LINEABOVE", (0, idx), (-1, idx), 0.5, C_STROKE))
    totals_tbl.setStyle(TableStyle(t_style))

    total_outer = Table(
        [[items_count, totals_tbl]],
        colWidths=[W - 76*mm, 76*mm],
    )
    total_outer.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(total_outer)
    story.append(Spacer(1, 4*mm))

    # ── Total in words ────────────────────────────────────────────────
    if num2words:
        try:
            words = num2words(int(total_round), lang="en_IN").title()
            words_str = f"Indian Rupee {words} Only"
        except Exception:
            words_str = f"Rs. {total_round:,.2f}"
    else:
        words_str = f"Rs. {total_round:,.2f}"

    story.append(Paragraph(f"<b>Total In Words</b>", s_muted))
    story.append(Paragraph(f"<i>{words_str}</i>", s_body))
    story.append(Spacer(1, 4*mm))

    # ── Authorized Signature ──────────────────────────────────────────
    sig_tbl = Table([[
        Spacer(1, 1),
        Paragraph("Authorized Signature",
                  ps("sig", fontSize=9, fontName="Helvetica", textColor=C_MUTED, alignment=TA_RIGHT)),
    ]], colWidths=[W - 50*mm, 50*mm])
    sig_tbl.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 6*mm))

    # ══════════════════════════════════════════════════════════════════
    #  PAYMENT RECEIVED BANNER
    # ══════════════════════════════════════════════════════════════════
    banner_text = "&#10003;  ADVANCE PAYMENT RECEIVED" if invoice_type == "advance" else "&#10003;  PAYMENT RECEIVED"
    banner = Table(
        [[Paragraph(
            banner_text,
            ps("paid", fontSize=11, fontName="Helvetica-Bold",
               textColor=C_GREEN, alignment=TA_CENTER),
        )]],
        colWidths=[W],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F0FFF6")),
        ("BOX",           (0, 0), (-1, -1), 1, colors.HexColor("#A8E6BF")),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(banner)
    story.append(Spacer(1, 6*mm))

    # ══════════════════════════════════════════════════════════════════
    #  FOOTER
    # ══════════════════════════════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=1, color=C_STROKE))
    story.append(Spacer(1, 3*mm))
    footer = Table([[
        Paragraph("HUEZO — Fashion Manufacturing",
                  ps("f1", fontSize=8, fontName="Helvetica-Bold", textColor=C_MUTED)),
        Paragraph("huezo.in  |  support@huezo.in",
                  ps("f2", fontSize=8, fontName="Helvetica",
                     textColor=C_MUTED, alignment=TA_RIGHT)),
    ]], colWidths=[W / 2, W / 2])
    footer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(footer)

    doc.build(story)
    return buffer.getvalue()


def generate_po_summary_pdf(order, profile):
    # ── Colours ────────────────────────────────────────────────────────
    C_DARK   = colors.HexColor("#1C0A0C")
    C_BURNT  = colors.HexColor("#341417")
    C_STROKE = colors.HexColor("#EDE8E3")
    C_MUTED  = colors.HexColor("#8A7F7A")
    C_WARM   = colors.HexColor("#F3EDE6")
    C_GREEN  = colors.HexColor("#2E9E55")
    C_WHITE  = colors.white
    C_LIGHT  = colors.HexColor("#F9F5F2")

    # ── Helpers ────────────────────────────────────────────────────────
    def humanise(s):
        return s.replace("_", " ").title() if s else "—"

    def fmt_date(dt):
        if not dt:
            return "—"
        try:
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return str(dt)

    def ps(name, **kwargs):
        return ParagraphStyle(name, **kwargs)

    # ── Document setup ─────────────────────────────────────────────────
    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm,  bottomMargin=15*mm,
    )
    W     = doc.width
    story = []

    s_body  = ps("body",  fontSize=9,  fontName="Helvetica",      textColor=C_DARK,  leading=13)
    s_muted = ps("muted", fontSize=8,  fontName="Helvetica",      textColor=C_MUTED, leading=12)
    s_bold  = ps("bold",  fontSize=9,  fontName="Helvetica-Bold", textColor=C_DARK,  leading=13)
    s_right = ps("right", fontSize=9,  fontName="Helvetica",      textColor=C_DARK,  alignment=TA_RIGHT)
    s_rbold = ps("rbold", fontSize=9,  fontName="Helvetica-Bold", textColor=C_DARK,  alignment=TA_RIGHT)

    def th(align=TA_LEFT):
        return ps(f"th{align}", fontSize=8, fontName="Helvetica-Bold",
                  textColor=C_WHITE, alignment=align)

    # ══════════════════════════════════════════════════════════════════
    #  HEADER — Logo left, PO SUMMARY right
    # ══════════════════════════════════════════════════════════════════
    logo_path = os.path.join(django_settings.BASE_DIR, "static", "images", "logo.png")
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=28*mm, height=28*mm, kind="proportional")
        logo_cell = logo_img
    else:
        logo_cell = Paragraph("<b>HUEZO</b>",
                               ps("fb", fontSize=20, fontName="Helvetica-Bold", textColor=C_BURNT))

    hdr = Table([[
        logo_cell,
        Table([[
            Paragraph("<b>PO SUMMARY</b>",
                      ps("ti", fontSize=20, fontName="Helvetica-Bold",
                         textColor=C_BURNT, alignment=TA_RIGHT)),
        ]], colWidths=[W * 0.6]),
    ]], colWidths=[W * 0.4, W * 0.6])
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width="100%", thickness=2, color=C_BURNT))
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  COMPANY INFO + ORDER META (two columns)
    # ══════════════════════════════════════════════════════════════════
    company_lines = [
        Paragraph("<b>HUEZO Fashion Manufacturing</b>",
                  ps("cn", fontSize=10, fontName="Helvetica-Bold", textColor=C_DARK)),
        Paragraph("huezo.in  |  support@huezo.in",  s_muted),
    ]

    meta_rows = [
        ("PO Number",     order.order_number),
        ("PO Date",       fmt_date(order.created_at)),
        ("Order Type",    humanise(order.order_type)),
    ]
    if order.garment_type:
        meta_rows.append(("Garment", order.garment_type))
    if order.for_category:
        meta_rows.append(("Category", humanise(order.for_category)))

    meta_tbl = Table(
        [[Paragraph(k, s_muted), Paragraph(v, s_bold)] for k, v in meta_rows],
        colWidths=[30*mm, W/2 - 34*mm],
    )
    meta_tbl.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
    ]))

    info_col = Table([[p] for p in company_lines], colWidths=[W/2 - 4*mm])
    top_row  = Table([[info_col, meta_tbl]], colWidths=[W/2, W/2])
    top_row.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(top_row)
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  CUSTOMER INFO
    # ══════════════════════════════════════════════════════════════════
    brand_name   = getattr(profile, "brand_name",   None) or ""
    contact_name = getattr(profile, "contact_name", None) or ""
    phone        = getattr(profile, "phone",        None) or ""
    address      = ""
    if profile:
        try:
            fa = profile.full_address
            address = fa() if callable(fa) else (fa or "")
        except Exception:
            pass

    def addr_block(title):
        rows = [[Paragraph(f"<b>{title}</b>",
                           ps(title, fontSize=9, fontName="Helvetica-Bold", textColor=C_WHITE))]]
        if brand_name:
            rows.append([Paragraph(f"<b>{brand_name}</b>", s_bold)])
        if contact_name:
            rows.append([Paragraph(contact_name, s_body)])
        if address:
            rows.append([Paragraph(address, s_muted)])
        if phone:
            rows.append([Paragraph(phone, s_body)])
        tbl = Table(rows, colWidths=[W/2 - 4*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  C_BURNT),
            ("TOPPADDING",    (0, 0), (-1, 0),  6),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 1), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_STROKE),
        ]))
        return tbl

    addr_row = Table([[addr_block("Bill To"), addr_block("Ship To")]],
                     colWidths=[W/2, W/2])
    addr_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",  (1, 0), (1, -1),  4),
    ]))
    story.append(addr_row)
    story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  ORDER SPECIFICATIONS
    # ══════════════════════════════════════════════════════════════════
    specs_data = []
    
    if order.order_type == "white_label" and order.white_label_catalogue:
        specs_data.append([Paragraph("Prototype Code", s_muted), Paragraph(order.white_label_catalogue.prototype_code, s_bold)])
    elif order.order_type == "fabrics" and order.fabric_catalogue:
        specs_data.append([Paragraph("Fabric Catalogue", s_muted), Paragraph(order.fabric_catalogue.fabric_name, s_bold)])
    
    if order.style_name:
        specs_data.append([Paragraph("Style Name", s_muted), Paragraph(order.style_name, s_bold)])
        
    specs_data.append([Paragraph("Total Quantity", s_muted), Paragraph(f"{order.total_quantity} {'meters' if order.order_type == 'fabrics' else 'pcs'}", s_bold)])
    
    if order.moq:
        specs_data.append([Paragraph("MOQ Requirement", s_muted), Paragraph(str(order.moq), s_body)])

    if order.order_type == "fabrics":
        specs_data.append([Paragraph("Swatch Required", s_muted), Paragraph("Yes" if order.swatch_required else "No", s_body)])

    if order.customization_notes:
        specs_data.append([Paragraph("Customization Notes", s_muted), Paragraph(order.customization_notes, s_body)])

    if order.message:
        specs_data.append([Paragraph("Fabric Sourcing Message", s_muted), Paragraph(order.message, s_body)])

    specs_table = Table(specs_data, colWidths=[50*mm, W - 50*mm])
    specs_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.5, C_STROKE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))

    story.append(Paragraph("<b>Order Specifications</b>", ps("sh", fontSize=11, fontName="Helvetica-Bold", textColor=C_BURNT)))
    story.append(Spacer(1, 2*mm))
    story.append(specs_table)
    story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  SIZE BREAKDOWN TABLE
    # ══════════════════════════════════════════════════════════════════
    if order.size_breakdown:
        size_headers = [Paragraph("<b>Size</b>", th(TA_CENTER)), Paragraph("<b>Quantity (pcs)</b>", th(TA_CENTER))]
        size_rows = [size_headers]
        
        for item in order.size_breakdown:
            if not isinstance(item, dict):
                continue
            size_val = str(item.get("size", "")).replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip()
            qty_val = str(item.get("quantity", 0))
            size_rows.append([
                Paragraph(size_val, ps("szc", fontSize=9, fontName="Helvetica-Bold", alignment=TA_CENTER)),
                Paragraph(qty_val, ps("szq", fontSize=9, fontName="Helvetica", alignment=TA_CENTER))
            ])
            
        size_rows.append([
            Paragraph("<b>Total</b>", ps("szt", fontSize=9, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(f"<b>{order.total_quantity}</b>", ps("sztq", fontSize=9, fontName="Helvetica-Bold", alignment=TA_CENTER))
        ])
        
        size_table = Table(size_rows, colWidths=[W/2, W/2])
        size_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_BURNT),
            ("GRID", (0, 0), (-1, -1), 0.5, C_STROKE),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, -1), (-1, -1), C_WARM),
        ]))
        
        story.append(Paragraph("<b>Size Breakdown</b>", ps("sh2", fontSize=11, fontName="Helvetica-Bold", textColor=C_BURNT)))
        story.append(Spacer(1, 2*mm))
        story.append(size_table)
        story.append(Spacer(1, 5*mm))

    # ══════════════════════════════════════════════════════════════════
    #  FINANCIAL DETAILS
    # ══════════════════════════════════════════════════════════════════
    cost_rows = []
    if order.unit_price:
        cost_rows.append(("Unit Rate", f"Rs. {order.unit_price}"))
    if order.gst_percentage:
        cost_rows.append(("GST Rate", f"{order.gst_percentage}%"))
    if order.total_amount:
        cost_rows.append(("Total Estimated Amount", f"Rs. {order.total_amount}"))
    if order.advance_amount:
        cost_rows.append(("Advance Amount", f"Rs. {order.advance_amount}"))

    if cost_rows:
        cost_table = Table(
            [[Paragraph(k, s_muted), Paragraph(v, s_bold)] for k, v in cost_rows],
            colWidths=[50*mm, W - 50*mm]
        )
        cost_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, C_STROKE),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(Paragraph("<b>Financial Details</b>", ps("sh3", fontSize=11, fontName="Helvetica-Bold", textColor=C_BURNT)))
        story.append(Spacer(1, 2*mm))
        story.append(cost_table)
        story.append(Spacer(1, 6*mm))

    # ══════════════════════════════════════════════════════════════════
    #  TERMS & CONDITIONS
    # ══════════════════════════════════════════════════════════════════
    terms_text = (
        "<b>Terms & Conditions:</b><br/>"
        "This PO Summary is automatically generated based on the order details confirmed by the customer through the Huezo App. "
        "Customers are requested to verify all specifications, quantities, sizes, and shipping details immediately upon receipt. "
        "Any modification request must be submitted to Huezo and may be subject to feasibility, additional charges, and revised delivery timelines. "
        "Production may commence based on this PO Summary, and changes requested after production initiation may not be accommodated. "
        "Failure to report discrepancies within 24 hours shall be deemed acceptance of the PO details."
    )
    story.append(Paragraph(terms_text, ps("terms", fontSize=7, fontName="Helvetica", textColor=C_MUTED, leading=10)))
    story.append(Spacer(1, 4*mm))

    # ══════════════════════════════════════════════════════════════════
    #  FOOTER
    # ══════════════════════════════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=1, color=C_STROKE))
    story.append(Spacer(1, 3*mm))
    footer = Table([[
        Paragraph("HUEZO — Fashion Manufacturing",
                  ps("f1", fontSize=8, fontName="Helvetica-Bold", textColor=C_MUTED)),
        Paragraph("huezo.in  |  support@huezo.in",
                  ps("f2", fontSize=8, fontName="Helvetica",
                     textColor=C_MUTED, alignment=TA_RIGHT)),
    ]], colWidths=[W / 2, W / 2])
    footer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(footer)

    doc.build(story)
    return buffer.getvalue()
