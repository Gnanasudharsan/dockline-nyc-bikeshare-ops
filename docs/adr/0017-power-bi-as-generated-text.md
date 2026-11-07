# 0017. Power BI as generated, validated text

- Status: Accepted
- Date: 2026-11-07

## Context
Power BI Desktop only runs on Windows; here it lives in a Windows 11 ARM VM while
development and Git stay on the Mac. `.pbix` files are binary and unreviewable. The
report must use the same metric definitions as Cube (ADR 0003), connect live to the
warehouse, and enforce borough-level access.

## Decision
- Use the **PBIP** format: a TMDL semantic model and a PBIR report. Both are plain
  text, and **`powerbi/build_pbip.py` generates them** from one Python spec, so a change
  is a reviewable diff. Lineage tags and names are deterministic UUIDs.
- **Mirror Cube by name.** Each fact table is named after a cube (`fleet_status`,
  `station_hourly`, `chronic_stations`), and each DAX measure has the name of a measure
  in that cube. A test fails if a visible DAX measure has no Cube twin.
- **DirectQuery** with `PostgreSQL.Database(DbHost & ":" & DbPort, DbName)`, using three
  parameters. A dedicated login, **`dockline_bi`**, can read only the **`bi` schema**:
  dbt views shaped for Power BI (local timestamps without time zone, integer keys, a
  borough table). An integration test keeps those views and the TMDL columns
  identical.
- **Row-level security:** one static role per borough, filtering `Borough`. The filter
  flows `Borough → Station → facts`.
- **Validation without Desktop**, in CI:
  1. every JSON file against Microsoft's published schemas (microsoft/json-schemas,
     pinned commit)
  2. the theme against Microsoft's theme schema
  3. every visual field, sort, filter, relationship, and RLS column against the model
  4. TMDL deserialized by Microsoft's own `TmdlSerializer` (.NET 8 console app)

  `VERIFY.md` covers what only Desktop can show: rendering, page refresh, and View as
  role. `BUILD_GUIDE.md` keeps a manual spec for each page in case one fails.
- Postgres is exposed to the VM through `POSTGRES_BIND_ADDRESS` set to the Mac's
  host-only interface address, never `0.0.0.0`.

## Consequences
- Every visual, measure, and relationship is reviewable in Git.
- The format of the page-refresh property is not specified in Microsoft's schemas, so
  it is the most likely thing to need a one-time fix in Desktop (VERIFY.md, step 6).
- Edits made in Desktop must be ported into the generator, or the next run overwrites
  them; a test enforces this.
