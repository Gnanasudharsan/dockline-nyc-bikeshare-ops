// Parity: the TypeScript KPIs (src/lib/metrics.ts) must equal the Python ones
// (ingestion/src/dockline_ingestion/kpis.py) on the same recorded GBFS poll. Both
// compare against tests/fixtures/gbfs_parity/expected.json. Run: npm run test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { computeLive, roundHalfAwayFromZero } from "../src/lib/metrics.ts";

const fixture = new URL("../../tests/fixtures/gbfs_parity/", import.meta.url);
const read = (name) => JSON.parse(readFileSync(new URL(name, fixture), "utf8"));

test("matches the Python implementation's expected output", () => {
  const { now_epoch: now } = read("case.json");
  const actual = computeLive(read("station_status.json"), read("station_information.json"), now);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(actual)), read("expected.json"));
});

test("rounds halves away from zero, like PostgreSQL", () => {
  assert.equal(roundHalfAwayFromZero(2.5), 3);
  assert.equal(roundHalfAwayFromZero(3.5), 4);
  assert.equal(roundHalfAwayFromZero(-2.5), -3);
});
