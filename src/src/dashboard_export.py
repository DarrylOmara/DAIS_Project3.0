import os
import logging
import numpy as np

logger = logging.getLogger("DAIS_Intraday.DashboardExport")

def build_dashboard_html(summary_list: list, cfg: dict, outdir: str) -> str:
    """
    Constructs a responsive, high-density HTML execution dashboard.
    Uses clean asset linking to maximize performance and prevent browser memory drag.
    """
    html_filename = os.path.join(outdir, "DAIS_Intraday_Performance_Dashboard.html")
    
    # Process lookback configuration metadata
    lookback = cfg.get('lookback_days', 30)
    interval = cfg.get('bar_interval', '5m')
    generated_at = os.popen('date').read().strip() if os.name != 'nt' else "2026-06-07" # Hard fallback if terminal access is blocked
    
    # ------------------------------------------------------------
    # CSS EMBEDDED FRAMEWORK ARCHITECTURE
    # ------------------------------------------------------------
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DAIS Project — High Frequency Engine Analytics Dashboard</title>
    <style>
        :root {{
            --bg-dark: #1e293b;
            --bg-light: #f8fafc;
            --slate-800: #0f172a;
            --slate-700: #334155;
            --emerald: #10b981;
            --crimson: #ef4444;
            --sky-blue: #0284c7;
            --text-main: #1e293b;
            --border-color: #e2e8f0;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-light);
            color: var(--text-main);
            line-height: 1.5;
            padding: 20px;
        }}
        header {{
            background: linear-gradient(135deg, var(--slate-800), var(--slate-700));
            color: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            margin-bottom: 24px;
        }}
        header h1 {{ font-size: 26px; font-weight: 800; margin-bottom: 6px; letter-spacing: -0.5px; }}
        .meta-strip {{ font-size: 13px; opacity: 0.85; font-weight: 500; }}
        
        .section-title {{ font-size: 18px; font-weight: 700; margin: 24px 0 12px 0; color: var(--slate-800); border-left: 4px solid var(--sky-blue); padding-left: 10px; }}
        
        /* High Performance Layout Flex Grid Containers */
        .summary-table-container {{
            background: white;
            padding: 16px;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            overflow-x: auto;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.05);
        }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }}
        th {{ background-color: var(--bg-dark); color: white; padding: 12px; font-weight: 600; }}
        td {{ padding: 12px; border-bottom: 1px solid var(--border-color); color: #475569; }}
        tr:nth-child(even) td {{ background-color: #f1f5f9; }}
        tr:hover td {{ background-color: #e2e8f0; }}
        .bold-ticker {{ font-weight: 700; color: var(--slate-800); }}

        /* Asset Specific Telemetry Layout Elements */
        .asset-card {{
            background: white;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.05);
        }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin-bottom: 16px; }}
        .card-header h3 {{ font-size: 18px; font-weight: 700; color: var(--sky-blue); }}
        
        .execution-pill-box {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }}
        .pill {{ padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background-color: #f1f5f9; border: 1px solid var(--border-color); }}
        .pill span {{ font-weight: 800; color: var(--slate-800); }}
        .pill.rejected-ma20 span {{ color: var(--crimson); }}
        .pill.rejected-cost span {{ color: var(--crimson); }}
        .pill.executed-sells span {{ color: var(--emerald); }}
        
        .image-flex-container {{ display: flex; flex-wrap: wrap; gap: 16px; justify-content: space-between; }}
        .img-box {{ flex: 1 1 calc(33.333% - 12px); min-width: 300px; border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; background: #fafafa; text-align: center; padding: 6px; }}
        .img-box img {{ max-width: 100%; height: auto; display: block; border-radius: 4px; margin: 0 auto; }}
        .img-label {{ font-size: 11px; color: #64748b; font-weight: 600; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
        
        @media(max-width: 1024px) {{ .img-box {{ flex: 1 1 calc(50% - 8px); }} }}
        @media(max-width: 768px) {{ .img-box {{ flex: 1 1 100%; }} }}
    </style>
</head>
<body>

    <header>
        <h1>DAIS Strategy Intraday Execution Platform</h1>
        <div class="meta-strip">System Log Generated: {generated_at} | Lookback Scan Range: {lookback} Days | Dynamic Sampling Granularity: {interval}</div>
    </header>

    <div class="section-title">Global Portfolio Performance Matrix</div>
    <div class="summary-table-container">
        <table>
            <thead>
                <tr>
                    <th>Asset Ticker</th>
                    <th>Total Return</th>
                    <th>Annualized Return</th>
                    <th>Sharpe Ratio</th>
                    <th>Maximum Drawdown</th>
                    <th>Calculated True Beta</th>
                    <th>Core / Base Trades Triggered</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # ------------------------------------------------------------
    # INJECT SUMMARY MATRIX TABLE GENERATOR
    # ------------------------------------------------------------
    for item in summary_list:
        ticker = item.get("ticker", "UNKNOWN")
        m = item.get("metrics", {})
        trade_stats = item.get("trade_stats", {})
        
        def fmt_pct(val):
            return f"{val * 100:.2f}%" if (val is not None and not np.isnan(val)) else "0.00%"
        def fmt_num(val):
            return f"{val:.2f}" if (val is not None and not np.isnan(val)) else "N/A"
            
        color_class = "style='color: var(--emerald); font-weight: 600;'" if m.get("total_return", 0) >= 0 else "style='color: var(--crimson); font-weight: 600;'"
        
        html_content += f"""
                <tr>
                    <td class="bold-ticker">{ticker}</td>
                    <td {color_class}>{fmt_pct(m.get("total_return"))}</td>
                    <td>{fmt_pct(m.get("annualized_return"))}</td>
                    <td><b>{fmt_num(m.get("sharpe"))}</b></td>
                    <td style="color: var(--crimson);">{fmt_pct(m.get("max_drawdown"))}</td>
                    <td>{fmt_num(item.get("beta_true"))}</td>
                    <td>{trade_stats.get('core_buys', 0)} Core / {trade_stats.get('base_buys', 0)} Base</td>
                </tr>"""

    html_content += """
            </tbody>
        </table>
    </div>

    <div class="section-title">Asset Level Execution Telemetry Streams</div>
    """

    # ------------------------------------------------------------
    # INJECT INDIVIDUAL ASSET BLOCK TELEMETRIES
    # ------------------------------------------------------------
    for item in summary_list:
        if "error" in item:
            continue
            
        ticker = item.get("ticker", "UNKNOWN")
        charts = item.get("charts", {})
        sell_stats = item.get("sell_rule_stats", {})
        
        # Build clean relative URL file pathways to utilize browser multi-thread rendering
        # This points down directly to the local file outputs generated by make_all_charts
        topo_rel = f"./{ticker}/{ticker}_execution_topology.png"
        equity_rel = f"./{ticker}/{ticker}_equity_curve.png"
        inventory_rel = f"./{ticker}/{ticker}_inventory_density.png"

        html_content += f"""
    <div class="asset-card">
        <div class="card-header">
            <h3>Asset Feed Node: {ticker}</h3>
        </div>
        
        <div class="execution-pill-box">
            <div class="pill executed-sells">Executed Sells: <span>{sell_stats.get('executed_sells', 0)}</span></div>
            <div class="pill">Overnight Liquidations: <span>{sell_stats.get('overnight_liquidations', 0)}</span></div>
            <div class="pill rejected-ma20">Rejected (Price &lt; MA20): <span>{sell_stats.get('rejected_ma20', 0)}</span></div>
            <div class="pill rejected-cost">Rejected (Price &lt; Cost Basis): <span>{sell_stats.get('rejected_avg_cost', 0)}</span></div>
        </div>

        <div class="image-flex-container">
            <div class="img-box">
                <img src="{topo_rel}" alt="{ticker} Topology" loading="lazy">
                <div class="img-label">MA Execution Strategy Topology</div>
            </div>
            <div class="img-box">
                <img src="{equity_rel}" alt="{ticker} Equity Curve" loading="lazy">
                <div class="img-label">Accumulated Equity Growth Curve</div>
            </div>
            <div class="img-box">
                <img src="{inventory_rel}" alt="{ticker} Inventory Density" loading="lazy">
                <div class="img-label">Intraday Share Inventory Allocation Density</div>
            </div>
        </div>
    </div>"""

    html_content += """
</body>
</html>
    """

    # Write out the clean dashboard payload string instantly
    try:
        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"High-frequency analytics web dashboard compiled safely at: {html_filename}")
        return html_filename
    except Exception as e:
        logger.error(f"Failed to compile dashboard string elements to disk: {e}", exc_info=True)
        raise e

