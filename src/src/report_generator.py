import os
import logging
from datetime import datetime
import pandas as pd
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

logger = logging.getLogger("DAIS_Intraday.ReportGenerator")

def build_pdf_report(summary_list: list, cfg: dict, outdir: str) -> str:
    """
    Constructs a professional, high-density PDF performance report from intraday metrics.
    Protects against malformed data inputs and memory leaks.
    """
    pdf_filename = os.path.join(outdir, "DAIS_Executive_Performance_Report.pdf")
    
    # Setup document geometry with safe defensive print margins
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom high-contrast palette styles for clear scannability
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#2c3e50"),
        spaceAfter=12
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2980b9"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#34495e")
    )
    
    table_text = ParagraphStyle(
        'TableText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#2c3e50")
    )
    
    table_header_text = ParagraphStyle(
        'TableHeaderText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white
    )

    story = []
    
    # ------------------------------------------------------------
    # EXECUTIVE HEADER BLOCK
    # ------------------------------------------------------------
    story.append(Paragraph("DAIS Project: Executive Analytics Brief", title_style))
    meta_string = f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | <b>Lookback Horizon:</b> {cfg.get('lookback_days', 30)} Days | <b>Interval:</b> {cfg.get('bar_interval', '5m')}"
    story.append(Paragraph(meta_string, body_style))
    story.append(Spacer(1, 15))
    
    # ------------------------------------------------------------
    # CROSS-ASSET CORE OVERVIEW SUMMARY MATRIX
    # ------------------------------------------------------------
    story.append(Paragraph("Portfolio Performance Summary Matrix", section_heading))
    
    # Define explicit columns: Ticker, Total Return, Ann. Return, Sharpe, MaxDD, True Beta, Trades Run
    matrix_data = [[
        Paragraph("Ticker", table_header_text),
        Paragraph("Total Return", table_header_text),
        Paragraph("Ann. Return", table_header_text),
        Paragraph("Sharpe Ratio", table_header_text),
        Paragraph("Max Drawdown", table_header_text),
        Paragraph("True Beta", table_header_text),
        Paragraph("Core / Base Buys", table_header_text)
    ]]
    
    for item in summary_list:
        ticker = item.get("ticker", "UNKNOWN")
        m = item.get("metrics", {})
        trade_stats = item.get("trade_stats", {})
        
        # Safe metric extraction helper to prevent layout formatting errors
        def fmt_pct(val):
            return f"{val * 100:.2f}%" if (val is not None and not np.isnan(val)) else "0.00%"
            
        def fmt_num(val, precision=2):
            return f"{val:.{precision}f}" if (val is not None and not np.isnan(val)) else "N/A"

        core_buys = trade_stats.get("core_buys", 0)
        base_buys = trade_stats.get("base_buys", 0)
        
        matrix_data.append([
            Paragraph(f"<b>{ticker}</b>", table_text),
            Paragraph(fmt_pct(m.get("total_return")), table_text),
            Paragraph(fmt_pct(m.get("annualized_return")), table_text),
            Paragraph(fmt_num(m.get("sharpe")), table_text),
            Paragraph(fmt_pct(m.get("max_drawdown")), table_text),
            Paragraph(fmt_num(item.get("beta_true")), table_text),
            Paragraph(f"{core_buys} / {base_buys}", table_text)
        ])
        
    # Build layout grid with explicit, un-stretchable boundaries
    matrix_table = Table(matrix_data, colWidths=[1.0*inch, 1.1*inch, 1.1*inch, 1.0*inch, 1.1*inch, 0.9*inch, 1.2*inch])
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
    ]))
    story.append(matrix_table)
    story.append(Spacer(1, 15))
    
    # ------------------------------------------------------------
    # ASSET SEGMENT VISUAL TELEMETRY CORES
    # ------------------------------------------------------------
    for item in summary_list:
        ticker = item.get("ticker", "UNKNOWN")
        charts = item.get("charts", {})
        sell_stats = item.get("sell_rule_stats", {})
        
        # Skip generating empty block rows if a ticker crashed inside a worker thread loop
        if "error" in item:
            continue
            
        asset_block = []
        asset_block.append(Paragraph(f"Asset Detailed Telemetry: {ticker}", section_heading))
        
        # Extract engine validation parameters
        exec_sells = sell_stats.get("executed_sells", 0)
        liq_sells = sell_stats.get("overnight_liquidations", 0)
        rej_ma20 = sell_stats.get("rejected_ma20", 0)
        rej_cost = sell_stats.get("rejected_avg_cost", 0)
        
        stats_string = (
            f"<b>Execution Summary Dynamics:</b> "
            f"Executed Sells: {exec_sells} | "
            f"Overnight Liquidations: {liq_sells} | "
            f"Rejected Orders (Below MA20): <font color='#e74c3c'>{rej_ma20}</font> | "
            f"Rejected Orders (Below Cost): <font color='#e74c3c'>{rej_cost}</font>"
        )
        asset_block.append(Paragraph(stats_string, body_style))
        asset_block.append(Spacer(1, 6))
        
        # Safely align charts inside layout containers
        topo_img = charts.get("topology")
        equity_img = charts.get("equity_curve")
        
        chart_data = []
        row_imgs = []
        
        if topo_img and os.path.exists(topo_img):
            row_imgs.append(Image(topo_img, width=3.6 * inch, height=1.65 * inch))
        if equity_img and os.path.exists(equity_img):
            row_imgs.append(Image(equity_img, width=3.6 * inch, height=1.65 * inch))
            
        if row_imgs:
            chart_data.append(row_imgs)
            chart_table = Table(chart_data, colWidths=[3.75*inch, 3.75*inch])
            chart_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            asset_block.append(chart_table)
            
        asset_block.append(Spacer(1, 10))
        
        # Enforce KeepTogether constraints to prevent orphan header rows at the bottom of pages
        story.append(KeepTogether(asset_block))
        
    try:
        doc.build(story)
        logger.info(f"High-frequency PDF summary constructed at: {pdf_filename}")
        return pdf_filename
    except Exception as e:
        logger.error(f"Failed to generate layout structures inside ReportLab: {e}", exc_info=True)
        raise e
