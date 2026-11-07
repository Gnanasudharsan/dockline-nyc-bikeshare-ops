# powerbi

Power BI Desktop project for analysts: **`Dockline.pbip`** (TMDL semantic model + PBIR
report), generated as text on the Mac by `build_pbip.py`, opened in Power BI Desktop in
a Windows 11 ARM VM. DirectQuery to the warehouse's `bi` schema with the read-only
`dockline_bi` login. Row-level security by borough. Five pages: Executive Summary, Live
Operations (auto page refresh), Station Performance, Weather Impact, Rebalancing.

DAX measures carry the same names as the Cube measures ([`dax/measures.md`](dax/measures.md)),
so Power BI, Grafana, the API, and the website agree on every number.

- **Open and check it:** [`VERIFY.md`](VERIFY.md)
- **How it is built and how to change it:** [`BUILD_GUIDE.md`](BUILD_GUIDE.md)
- **Design decision:** [ADR 0017](../docs/adr/0017-power-bi-as-generated-text.md)

```bash
make powerbi
```
```bash
make powerbi-validate
```
```bash
make powerbi-reference
```
