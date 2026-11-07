# Verify the Power BI project in Power BI Desktop

The project is generated and validated on the Mac:
- Microsoft's JSON schemas
- Microsoft's TMDL parser
- field checks
- a dbt contract test

What only Power BI Desktop can confirm is listed here. It takes about 15 minutes in the
Windows 11 ARM VM. Git stays on the Mac; the VM only opens the files.

## 0. Prerequisites

- Power BI Desktop (current release, from the Microsoft Store) in the Windows 11 ARM VM.
- The repository folder shared into the VM:
  - Parallels: *Shared Folders*.
  - UTM: a SPICE/VirtFS share or a synced folder.
- On the Mac, the stack is running (`make up`).
- On the Mac, Postgres is reachable from the VM network only (step 1).

## 1. Expose Postgres to the VM network, and only there (Mac)

Find the Mac's address on the VM's virtual network:

| Hypervisor | Interface on the Mac | Typical Mac address |
| --- | --- | --- |
| Parallels (Shared network) | `bridge100` / `prl_vnic0` | `10.211.55.2` |
| UTM (Shared network) | `bridge100` | `192.168.64.1` |

```bash
ifconfig bridge100 | grep "inet "
```

Then, in `.env`:

```
POSTGRES_BIND_ADDRESS=10.211.55.2
```

Use your address from above. **Never** `0.0.0.0`: that would expose the warehouse to
every network the Mac joins. Restart the warehouse:

```bash
docker compose up -d timescaledb
```

Postgres now listens on `10.211.55.2:5433` only, which is reachable from the VM and not
from your LAN or the internet. To go back to local-only, set it to `127.0.0.1` again.

## 2. Open the project (VM)

Open `powerbi\Dockline.pbip` from the shared folder. If Desktop asks to upgrade or
convert the report format, choose **upgrade**. Do **not** save as `.pbix`.

## 3. Point the parameters at the warehouse

*Transform data → Edit parameters*:

| Parameter | Value |
| --- | --- |
| `DbHost` | the Mac's VM-network address from step 1 (default `10.211.55.2`) |
| `DbPort` | `5433` (your `POSTGRES_PORT`) |
| `DbName` | `dockline` |

Then *Apply changes*. When asked for credentials, choose **Database**:
- user `dockline_bi`
- password: the value of `DOCKLINE_BI_PASSWORD` in the Mac's `.env`

If the connection fails with an SSL/encryption error: *File → Options and settings →
Data source settings → (the source) → Edit Permissions*, untick **Encrypt
connections**. The local warehouse has no TLS certificate; traffic stays on the
host-only network.

**Expected:** all 8 tables load in DirectQuery mode with no errors:
`fleet_status`, `station_hourly`, `chronic_stations`, `Station`, `Borough`, `Date`,
`Hour`, `Weather`.

## 4. Model checks (Model view)

- [ ] 7 relationships, all many-to-one, single direction:
  - `fleet_status`, `station_hourly` and `chronic_stations` → `Station`
  - `Station` → `Borough`
  - `station_hourly` → `Date`, `Hour` and `Weather`
- [ ] `Date` is marked as the date table (*Table tools → Mark as date table*, date
      column `calendar_date`). If it is not, mark it. The TMDL sets `dataCategory: Time`
      and `isKey`.
- [ ] Measures appear in display folders:
  - **fleet_status:** `Live\Availability`, `Live\Station counts`, `Live\Rebalancing`,
    `Live\Data quality`
  - **station_hourly:** `History\Minutes`, `History\Rates`, `History\Flow`
- [ ] Sort-by columns work: `Borough[borough]` sorts Manhattan → Hoboken, and
      `Hour[hour_label]` sorts 12 AM → 11 PM.

## 5. Numbers match Cube

On the Mac, while Desktop shows the report:

```bash
make powerbi-reference
```

- [ ] **Live Operations** cards and the *Right now by borough* table match the
      `fleet_status` values. Live numbers move by a few units between refreshes;
      refresh both to compare.
- [ ] **Executive Summary**, with the date slicer cleared: the *Availability rate by
      borough* bars and the cards match the "all history" values to 3 decimals.

Measures have the same names in both tools (`powerbi/dax/measures.md`), so compare them
name for name.

## 6. Automatic page refresh

- [ ] **Live Operations**: *Format page → Page refresh* is **On**, every **30 seconds**.
      Watch the *Data age (s)* card change.
- [ ] **Rebalancing**: page refresh is **On**, every **60 seconds**.

If either shows **Off**, Desktop did not accept the generated value (the format of
this property is not documented in Microsoft's schemas). Fix it in one minute:
1. In Desktop, turn it on and set the interval.
2. Save.
3. Copy the `pageRefresh` block that Desktop wrote into
   `Dockline.Report/definition/pages/<page>/page.json`, and tell me so I can update
   `build_pbip.py` to match.

## 7. Row-level security

*Modeling → View as*. For each role you check (at least Manhattan and Jersey City):

- [ ] Choose `Borough - Manhattan`. Every page shows only Manhattan: the borough
      slicer lists only Manhattan, and the Live Operations totals equal Cube's
      Manhattan row from step 5.
- [ ] Choose `Borough - Jersey City`, and check the same.
- [ ] Choose no role, and every borough is back.

## 8. Pages render

Each page should render without "Couldn't load the data" or "Fix this" errors:

| Page | What should be there |
| --- | --- |
| Executive Summary | Cards: availability, empty share, full share, bikes added, chronic stations. A date slicer. Daily line by borough. Borough bars. Hour-of-day columns. |
| Live Operations | 7 live cards. Stations by state. Borough table. High-traffic empty table. |
| Station Performance | Borough and date slicers. Station table sorted by availability (lowest first). Chronic verdict table. Two cards. |
| Weather Impact | Temperature, precipitation and availability cards. Availability by condition and by temperature band. Flow by condition. |
| Rebalancing | 4 cards. Borough slicer. Ranked visit queue (only stations that need a visit). Bikes to move by borough and state. |

If a page fails to render twice after the fixes above, stop. Use that page's
specification in `BUILD_GUIDE.md` ("Manual page specs") to build it by hand, and tell me
which visual failed.

## 9. Record the result

Note anything that differed in the "Verification log" at the end of this file, with the
date, the Desktop version, and what you changed. Commit from the Mac.

## Verification log

| Date | Desktop version | Result | Notes |
| --- | --- | --- | --- |
| | | | |
