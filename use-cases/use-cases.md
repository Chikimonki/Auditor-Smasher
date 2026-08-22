# Auditor Smasher: Use Cases for Companies House Data Sources

## Overview

Companies House provides three complementary data access methods. Each serves a different purpose in a procurement audit pipeline. This document outlines how Auditor Smasher can use them together.

---

## 1. Streaming API

### What it is
A persistent connection that pushes every change to company data in real-time as it happens.

### Use case: Real-time anomaly detection
- Subscribe to the streaming feed for filing events
- Detect when a company's officers change immediately after a contract award
- Flag sudden PSC (People of Significant Control) changes that could indicate beneficial ownership shifts
- Monitor for duplicate director appointments across competing suppliers in the same tender

### How Auditor Smasher would use it
```
Streaming API → Event processor → Anomaly scorer → Alert
```

Instead of polling the API every hour, the streaming feed pushes events to you. When a company wins a contract and then immediately changes its directors, you catch it in minutes, not days.

### Limitations
- Requires a persistent connection (WebSocket)
- No filtering by company type or region — you get everything
- Must maintain your own event queue and processing logic

---

## 2. Bulk Downloads

### What it is
Full CSV snapshots of all UK company data, updated daily or monthly. No rate limits.

### Use case: Baseline database and network mapping
- Download the complete companies dataset (~5 million records)
- Build a local database of all company-to-director relationships
- Map supplier networks: which companies share directors, addresses, or PSCs
- Establish baseline financial health metrics across sectors
- Pre-compute entity resolution (match company names across datasets)

### How Auditor Smasher would use it
```
Bulk Download → Local DB → Network graph → Supplier clustering
```

The bulk data gives you the full picture without hitting rate limits. You can load 5 million companies into PostgreSQL, build a NetworkX graph of director connections, and identify clusters of related suppliers — all offline.

### Available datasets
| Dataset | Update frequency | Size |
|---------|-----------------|------|
| Companies (basic) | Daily | ~5M rows |
| Officers | Daily | ~15M rows |
| PSCs | Daily | ~2M rows |
| Accounts | Monthly | ~10M rows |
| Filing history | Daily | ~50M rows |

### Limitations
- Data is a snapshot — no history of changes unless you collect daily
- CSV format requires parsing (no nested JSON)
- Some fields are empty or inconsistent across records

---

## 3. Filing Feed

### What it is
A chronological feed of every document filed with Companies House each day.

### Use case: Audit trail reconstruction
- Track the exact sequence of filings for any company
- Detect backdated filings or unusual filing patterns
- Identify companies that file accounts late (a red flag for financial distress)
- Cross-reference filing dates with contract award dates in public procurement data

### How Auditor Smasher would use it
```
Filing Feed → Timeline builder → Pattern detector → Risk score
```

If a company files its accounts 6 months late and then wins a major public contract, that's a risk signal. The filing feed lets you reconstruct the timeline and score the risk.

### Key filing types to monitor
- `AD01` — Change of registered office (could indicate shell company movement)
- `TM01` — Termination of director appointment
- `AP01` — Appointment of director (new faces after contract wins)
- `PSC01` — Person with significant control appointed
- `AA` — Annual accounts (late filing = risk signal)
- `RESOLUTIONS` — Special resolutions (could indicate restructuring)

### Limitations
- Feed is chronological only — no search or filtering
- Must process and store locally for analysis
- Historical filings require bulk download or API queries

---

## Combined Pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Bulk Downloads  │────▶│   Local Database  │◀────│  Filing Feed    │
│  (baseline)      │     │  (PostgreSQL)     │     │  (daily update) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │  Network Graph   │
                       │  (NetworkX)      │
                       └──────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ Streaming API    │
                       │ (real-time)      │
                       └──────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ Anomaly Alerts   │
                       │ (Streamlit UI)   │
                       └──────────────────┘
```

### Workflow
1. **Bulk Downloads** — Load all company, officer, and PSC data into a local database. Build the supplier network graph.
2. **Filing Feed** — Each day, append new filings to the database. Update risk scores based on filing patterns.
3. **Streaming API** — Monitor for real-time changes. When a company's officers or PSCs change, cross-reference against the network graph to detect anomalies.
4. **Output** — Streamlit dashboard shows flagged anomalies with supporting evidence.

---

## Why All Three Matter

| Method | Speed | Coverage | Use |
|--------|-------|----------|-----|
| Bulk Downloads | Slow (batch) | Complete snapshot | Baseline, network mapping |
| Filing Feed | Daily | Chronological | Audit trail, pattern detection |
| Streaming API | Real-time | All changes | Anomaly alerts |

No single method covers all audit scenarios. Together, they provide:
- Historical context (bulk)
- Temporal patterns (filings)
- Immediate detection (streaming)

This is the foundation for a procurement audit tool that doesn't just look at point-in-time data but understands the relationships and timing of corporate changes.

---

## Technical Notes

### API Key: Same for REST and Streaming
You do **not** need a new API key to use the Streaming API. The same Companies House API key works for both REST and Streaming endpoints:
- REST: `api.company-information.service.gov.uk`
- Streaming: `api-stream.company-information.service.gov.uk`

No account changes required — just point your code at the streaming endpoint.

### Bulk Data: One Way to Get It
The CSV download from http://download.companieshouse.gov.uk/en_output.html is the **only** official method for bulk data. There is no:
- Bulk API endpoint
- Filtered download (e.g., "all construction companies")
- Programmatic request for subsets

You download the full ~470MB zip, unzip it, and load it into your own database. If you need filtered data, you filter locally after download.

---

## What's Missing: Gaps in Companies House Data Access

These are features that would improve Auditor Smasher but are not currently available from Companies House.

### GraphQL API
**What it means:** The current REST API returns fixed data structures. If you want company info + officers + filings in one request, you make three separate calls. GraphQL lets you specify exactly which fields you want across multiple resources in a single query.

**Impact on Auditor Smasher:** You could fetch a company, its directors, and its filing history in one request instead of three. This reduces API calls (less rate limit pressure) and simplifies code.

**Workaround today:** Make multiple REST calls and merge the results in your code. Use bulk downloads where possible to avoid the API entirely.

### Webhooks
**What it means:** Currently you either poll the API repeatedly (wasteful) or use the Streaming API (gets everything, no filtering). Webhooks would let Companies House push specific events to a URL you define — e.g., "notify me when company X changes its directors."

**Impact on Auditor Smasher:** You could monitor only the companies in your audit scope instead of processing the entire national stream. Less data to process, faster alerts.

**Workaround today:** Use the Streaming API and filter events client-side. Build your own event queue and discard irrelevant events.

### Bulk Data Filtering by Sector
**What it means:** The bulk downloads contain all 5.1M UK companies. If you only need companies in a specific sector (e.g., NHS suppliers, construction), you must download everything and filter locally.

**Impact on Auditor Smasher:** A filtered endpoint would reduce download size from 470MB to potentially a few MB for a specific sector. Faster setup, less storage.

**Workaround today:** Download the full dataset, filter by SIC code (Standard Industrial Classification) in your database, and discard the rest.
