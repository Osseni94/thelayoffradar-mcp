# LMI MCP Server

Model Context Protocol server exposing TheLayoffRadar's **Labor Market Intelligence** dataset to AI clients (Claude Desktop, Cursor, Claude Code, any MCP-compatible app).

## What it does

Hedge fund analysts and their AI agents can query workforce signals conversationally:

> "What's the current workforce stress index for Verizon, and when did the last signal spike precede a confirmed layoff?"

The LLM calls the MCP tools below and returns structured answers grounded in live data.

## Tools

| Tool | Purpose |
|---|---|
| `list_companies` | Discover available tickers + headline stats |
| `get_dashboard` | Top-level screen for the 11 core companies |
| `get_company_signals` | Full monthly time-series for one company |
| `get_company_layoffs` | Confirmed layoff events (ground truth) |
| `get_company_overlay` | Signals + layoffs combined (chart-ready) |
| `get_company_categories` | Category breakdown with trend |
| `get_company_keywords` | Trending keywords + sentiments |
| `get_signal_lag_analysis` | Signal-to-event lag proof |
| `export_dataset_csv_url` | Build a direct CSV download URL |

## Resources

| URI | Content |
|---|---|
| `lmi://methodology` | Full methodology note |
| `lmi://coverage` | Live dataset coverage table |

## Install

```bash
pip install -r requirements.txt
```

## Run standalone

```bash
python server.py
```

The server communicates over stdio.

## Configure in Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "labor-market-intelligence": {
      "command": "python",
      "args": ["C:/Users/User/Layoff_Radar/mcp_server/server.py"]
    }
  }
}
```

Then restart Claude Desktop. The tools will appear in the app.

## Configure in Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "labor-market-intelligence": {
      "command": "python",
      "args": ["C:/Users/User/Layoff_Radar/mcp_server/server.py"]
    }
  }
}
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LMI_API_BASE` | `https://thelayoffradar-api.fly.dev/api/labor-intel` | API base URL (override for staging) |
| `LMI_API_KEY` | *(unset)* | Reserved for future authentication |

## Data source

All tools call the public TheLayoffRadar LMI API. No local SQLite required — the server is just a thin protocol bridge. This keeps distribution simple: clients only need Python + two dependencies.

## Coverage

- **Product universe:** Fortune 500 companies + any custom tickers requested per contract
- **Demo subset** currently loaded in the public API (curated examples for prospect demos); licensed clients receive their contracted coverage list
- Monthly signals from 2017 to present
- 60,000+ NLP-processed documents and growing
- Confirmed layoff events sourced from WARN filings, SEC disclosures, and news
- Methodology is identical across all companies — adding a new ticker is a data-ingestion task, not a modeling change

Use `list_companies` to see which tickers are currently active on your licensed instance.

## Licensing

Contact admin@grandnasser.com for commercial licensing, custom ticker requests, and full Fortune 500 coverage.
