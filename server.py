"""
Labor Market Intelligence MCP Server

Exposes TheLayoffRadar's Labor Market Intelligence dataset as MCP tools
so hedge fund analysts (and their AI agents) can query workforce signals,
confirmed layoff events, signal-to-event lag, and more — directly from
Claude, Cursor, or any MCP-compatible client.

Data source: TheLayoffRadar LMI API (https://thelayoffradar-api.fly.dev)
Coverage: Fortune 500 universe + custom companies on request.
A curated demo subset is currently live; licensed clients receive expanded
coverage (full Fortune 500 plus any custom tickers specified in their
contract) with the same signal methodology applied.

Transport: stdio (works with Claude Desktop config, Cursor, etc.)
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get(
    "LMI_API_BASE",
    "https://thelayoffradar-api.fly.dev/api/labor-intel",
)
API_KEY = os.environ.get("LMI_API_KEY")  # reserved for future auth
TIMEOUT = 30.0

mcp = FastMCP(
    "labor-market-intelligence",
    instructions=(
        "TheLayoffRadar Labor Market Intelligence dataset. "
        "Use these tools to retrieve hedge-fund-grade workforce signals "
        "across Fortune 500 companies (plus any custom tickers added "
        "for a client). Signals are NLP-extracted from employee-forum "
        "posts and validated against confirmed layoff events. Each "
        "signal carries a confidence label (LOW/MED/HIGH) that reflects "
        "sample size. Always present confidence alongside numeric values "
        "when quoting to the user. Use list_companies first to discover "
        "which tickers are currently loaded for this client."
    ),
)


def _headers() -> dict[str, str]:
    h = {"User-Agent": "lmi-mcp/1.0", "Accept": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


async def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE}{path}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


# ────────────────────────────────────────────────────────────
# Tools — each wraps an underlying LMI API endpoint
# ────────────────────────────────────────────────────────────


@mcp.tool()
async def list_companies() -> list[dict]:
    """
    List all companies in the Labor Market Intelligence dataset with
    headline stats (total months, signal volume, average workforce stress
    index, latest signal date). Use this as a starting point to discover
    which tickers are available.

    Returns a list of companies sorted by average stress index (highest first).
    """
    return await _get("/companies")


@mcp.tool()
async def get_dashboard() -> list[dict]:
    """
    Get the top-level dashboard summary for the client's active coverage
    universe. The dashboard surfaces the most operationally useful view:
    current stress, 3-month averages, and signal-vs-event accuracy per
    company.

    For each company, returns:
      - current_stress_index: latest WSI (0-100)
      - stress_trend: rising / falling / stable (3m vs prior 3m)
      - avg_negativity_3m, layoff_signal_pct_3m, departure_intent_pct_3m
      - total_confirmed_layoffs, total_employees_affected
      - signal_accuracy_pct: % of layoff events preceded by WSI spike

    Ideal for a weekly/daily screen. Sorted by current stress index
    descending. Use list_companies if you need the full universe instead
    of this curated dashboard.
    """
    return await _get("/dashboard")


@mcp.tool()
async def get_company_signals(ticker: str) -> list[dict]:
    """
    Get the full monthly time-series of workforce stress signals for a
    company. Each row is one month and contains:

      - workforce_stress_index (0-100): composite labor stress score
      - avg_negativity, max_negativity
      - layoff_signal_pct, departure_intent_pct (both 0-1, Bayesian-smoothed)
      - signal_confidence (0-1) + signal_confidence_label (LOW/MED/HIGH)
      - dominant_sentiment
      - category scores: org_stability, workload_pressure, compensation_risk,
        career_development, culture
      - signal_volume, post_count, comment_count

    Args:
      ticker: Stock ticker (e.g., "VZ", "AMZN", "MSFT"). Case-insensitive.

    Returns months in chronological order.
    """
    return await _get(f"/company/{ticker.upper()}/signals")


@mcp.tool()
async def get_company_daily_signals(
    ticker: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """
    Get DAILY workforce stress signals for a company. This is the
    quant-grade endpoint — each row is one calendar day.

    Use this when the user asks for daily resolution, recent activity,
    event detection, or "what was happening around date X". For trend
    analysis over years, use get_company_signals (monthly) instead.

    Each row contains:
      - content_date (YYYY-MM-DD)
      - post_count, comment_count, signal_volume
      - avg_negativity, max_negativity
      - layoff_signal_pct_raw / layoff_signal_pct_raw_raw: raw rates (unsmoothed)
      - layoff_signal_pct / departure_intent_pct: Bayesian-smoothed, volume-weighted
      - workforce_stress_index (0-100)
      - signal_confidence + signal_confidence_label (LOW/MED/HIGH)
      - dominant_sentiment

    Only days with actual NLP data are returned (sparse representation).

    Args:
      ticker: Stock ticker, case-insensitive.
      from_date: Start date YYYY-MM-DD (inclusive). Defaults to 90 days ago.
      to_date: End date YYYY-MM-DD (inclusive). Defaults to today.
    """
    params: dict[str, Any] = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    return await _get(
        f"/company/{ticker.upper()}/signals/daily",
        params=params or None,
    )


@mcp.tool()
async def get_company_layoffs(ticker: str) -> list[dict]:
    """
    Get all confirmed layoff events for a company (announcement date,
    employees affected, divisions, reason, source).

    These are the ground-truth events used to validate signal accuracy.

    Args:
      ticker: Stock ticker. Case-insensitive.
    """
    return await _get(f"/company/{ticker.upper()}/layoffs")


@mcp.tool()
async def get_company_overlay(ticker: str) -> dict:
    """
    Get a combined signals + confirmed-layoffs payload for charting.
    Useful when you want to see the stress-index time series alongside
    the actual layoff announcement markers in a single call.

    Args:
      ticker: Stock ticker. Case-insensitive.

    Returns: {company, ticker, signals: [...], layoffs: [...]}
    """
    return await _get(f"/company/{ticker.upper()}/overlay")


@mcp.tool()
async def get_company_categories(ticker: str, months: int = 6) -> list[dict]:
    """
    Get the category breakdown for a company over the last N months.
    Categories are: organizational_stability, workload_pressure,
    compensation_benefits, career_development, work_environment_culture,
    and others (industry_specific, customer_market_discontent, etc.).

    Each category reports avg_score, recent_score, and trend (up/down/stable)
    by comparing the recent half of the window to the older half.

    Args:
      ticker: Stock ticker. Case-insensitive.
      months: Window size in months (1-120). Default 6.
    """
    return await _get(
        f"/company/{ticker.upper()}/categories", params={"months": months}
    )


@mcp.tool()
async def get_company_keywords(ticker: str, months: int = 6) -> dict:
    """
    Get trending keywords and sentiments for a company over the last N
    months. Useful for qualitative narrative around the numeric signals.

    Args:
      ticker: Stock ticker. Case-insensitive.
      months: Window size in months (1-120). Default 6.

    Returns: {keywords: [...], sentiments: [...]}
    Each item has {label, count, avg_score}.
    """
    return await _get(
        f"/company/{ticker.upper()}/keywords", params={"months": months}
    )


@mcp.tool()
async def get_signal_lag_analysis(ticker: str) -> list[dict]:
    """
    Get the signal-to-event lag analysis for each confirmed layoff event
    at this company. For each event, returns the 1-6 month pre-announcement
    window showing workforce_stress_index, avg_negativity, layoff_signal_pct,
    and the earliest month where a stress spike (>120% of baseline) was
    detected.

    This is the proof-of-predictive-value analysis. Use it to quote
    specific lead times like "signal spiked N months before announcement."

    Args:
      ticker: Stock ticker. Case-insensitive.
    """
    return await _get(f"/company/{ticker.upper()}/signal-lag")


@mcp.tool()
async def request_custom_ticker(
    ticker: str,
    company_name: str | None = None,
    rationale: str | None = None,
) -> dict:
    """
    Request that a new ticker be added to this client's LMI coverage.
    Use this when the user asks about a company that is not returned by
    list_companies. This does NOT add the ticker automatically — it
    returns a ready-to-send request message and the contact address.

    Coverage is contract-scoped: any Fortune 500 company (and most
    custom tickers) can be added with the same signal methodology.
    Typical turnaround is a few days for data ingestion + NLP processing.

    Args:
      ticker: Ticker symbol being requested (e.g., "ORCL").
      company_name: Optional company display name for clarity.
      rationale: Optional one-liner — why this company matters to the
                 client's thesis. Helps prioritize the request.

    Returns a structured payload the calling LLM can format for the user.
    """
    ticker = ticker.upper().strip()
    return {
        "status": "not_in_coverage",
        "ticker": ticker,
        "company_name": company_name,
        "message": (
            f"{ticker} is not in this client's active LMI coverage. "
            "TheLayoffRadar can add any Fortune 500 company (and most "
            "custom tickers) to your licensed instance. New ticker "
            "ingestion typically takes a few business days and applies "
            "the same signal methodology used across the rest of the "
            "dataset."
        ),
        "next_step": "Contact admin@grandnasser.com to request this ticker.",
        "contact_email": "admin@grandnasser.com",
        "rationale_received": rationale,
        "estimated_turnaround_days": "3-7 business days",
    }


@mcp.tool()
async def export_dataset_csv_url(ticker: str | None = None) -> dict:
    """
    Build a direct CSV download URL for the dataset. MCP clients that
    need to feed data into a spreadsheet or a separate analysis pipeline
    can fetch this URL directly.

    Columns: company, ticker, date, signal_volume, workforce_stress_index,
    sentiment_pressure_index, layoff_probability_signal, attrition_risk_signal,
    dominant_sentiment, signal_confidence, org_stability_score,
    workload_pressure_score, compensation_risk_score, career_development_score,
    culture_score.

    Args:
      ticker: Optional stock ticker to filter. If omitted, returns all companies.

    Returns: {url, filename, columns}
    """
    base = API_BASE
    if ticker:
        url = f"{base}/export/csv?ticker={ticker.upper()}"
        filename = f"labor_intel_{ticker.upper()}.csv"
    else:
        url = f"{base}/export/csv"
        filename = "labor_intel_all_companies.csv"
    return {
        "url": url,
        "filename": filename,
        "columns": [
            "company",
            "ticker",
            "date",
            "signal_volume",
            "workforce_stress_index",
            "sentiment_pressure_index",
            "layoff_probability_signal",
            "attrition_risk_signal",
            "dominant_sentiment",
            "signal_confidence",
            "org_stability_score",
            "workload_pressure_score",
            "compensation_risk_score",
            "career_development_score",
            "culture_score",
        ],
    }


# ────────────────────────────────────────────────────────────
# Resources — context documents the client can read on demand
# ────────────────────────────────────────────────────────────


@mcp.resource("lmi://methodology")
def methodology() -> str:
    """Full methodology note for the LMI dataset."""
    return (
        "TheLayoffRadar Labor Market Intelligence — Methodology\n"
        "========================================================\n\n"
        "Sources:\n"
        "  - Reddit (r/Layoffs + company-specific subreddits, 2017-present)\n"
        "  - TheLayoff.com employee forums (Wayback Machine + live scrape)\n"
        "  - Confirmed layoff events (WARN filings, SEC, news)\n\n"
        "NLP pipeline:\n"
        "  - KeyNeg Enterprise (sentence-transformers + cosine similarity)\n"
        "  - Custom negative-sentiment taxonomy (organizational_stability,\n"
        "    workload_pressure, compensation_benefits, career_development,\n"
        "    work_environment_culture)\n"
        "  - Temporal filtering: past-tense references weighted 0.3x\n\n"
        "Signal correction (3 layers):\n"
        "  1. Volume-weighted probability: min(1, log(v+1)/log(20))\n"
        "  2. Bayesian smoothing: (mentions+2) / (volume+10)\n"
        "  3. Hard cap: 35% max for volume < 5\n\n"
        "Confidence scoring:\n"
        "  confidence = min(1, log(volume+1) / log(50))\n"
        "  label: LOW (<0.3) / MED (0.3-0.6) / HIGH (>0.6)\n\n"
        "Workforce Stress Index:\n"
        "  WSI = min(100, avg_negativity * 100 * (1 + layoff_signal_pct))\n\n"
        "Signal accuracy:\n"
        "  % of confirmed layoff events (100+ employees) preceded by a WSI\n"
        "  spike exceeding 120% of company baseline within 90 days prior to\n"
        "  the announcement date.\n"
    )


@mcp.resource("lmi://coverage")
async def coverage() -> str:
    """Live dataset coverage for this client (generated from the API)."""
    companies = await _get("/companies")
    lines = [
        "TheLayoffRadar LMI — Active Coverage (this client)",
        "=" * 55,
        "",
        "This resource lists the tickers currently loaded for your",
        "licensed instance. Product universe is Fortune 500 + any custom",
        "companies specified in your contract; contact admin@grandnasser.com",
        "to request additional tickers.",
        "",
    ]
    lines.append(f"Active companies: {len(companies)}")
    lines.append("")
    lines.append(
        f"{'Ticker':<8}{'Company':<22}{'Months':>8}{'Volume':>10}{'Latest':>14}"
    )
    lines.append("-" * 62)
    for c in companies:
        lines.append(
            f"{c['ticker']:<8}{c['company']:<22}"
            f"{c['total_months']:>8}{c['total_signals']:>10}"
            f"{c.get('latest_date') or '-':>14}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
