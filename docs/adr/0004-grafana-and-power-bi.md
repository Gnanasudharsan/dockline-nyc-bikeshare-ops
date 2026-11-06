# 0004. Grafana for live ops, Power BI for analysis

- Status: Accepted
- Date: 2026-11-06

## Context
Two audiences: an operator who needs a wall screen that refreshes every few seconds and
alerts, and an analyst or executive who needs slicing, drill-through, row-level
security, and a familiar enterprise BI tool.

## Decision
Use Grafana OSS for live operations (provisioned as code, alert rules as code, public
dashboards for website embedding) and Power BI Desktop for analysis (Power BI Project
format: TMDL model and PBIR report committed as text, DirectQuery with automatic page
refresh).

## Consequences
- Each tool does what it is best at; the shared design tokens make them look like one product.
- Two BI surfaces to maintain; metric parity relies on ADR 0003.
- Power BI Desktop is Windows-only, so development uses a Windows 11 ARM VM; files are
  generated on the Mac and only opened in the VM. Publishing to Power BI Service is out of
  scope (requires a paid or work tenant).
