import type { Page } from "@playwright/test";

const API = "http://localhost:8070";

export const kpis = {
  as_of: "2026-11-07T21:00:00+00:00",
  bikes_available: 32458,
  ebikes_available: 14287,
  docks_available: 33753,
  fill_ratio: 0.49,
  stations: 2520,
  stations_in_service: 2424,
  empty_stations: 142,
  full_stations: 166,
  starving_stations: 685,
  balanced_stations: 1141,
  flooding_stations: 598,
  offline_stations: 96,
  rebalance_need_bikes: 15202,
  data_freshness_seconds: 64,
};

export const stations = {
  as_of: kpis.as_of,
  count: 2,
  stations: [
    {
      station_id: "a",
      station_name: "W 4 St & 7 Ave",
      borough: "Manhattan",
      latitude: 40.734,
      longitude: -74.002,
      imbalance_state: "starving",
      station_bikes_available: 0,
      station_docks_available: 22,
    },
    {
      station_id: "b",
      station_name: "Court St & State St",
      borough: "Brooklyn",
      latitude: 40.69,
      longitude: -73.992,
      imbalance_state: "flooding",
      station_bikes_available: 30,
      station_docks_available: 1,
    },
  ],
};

/** Route every API call the browser makes to fixtures (server-side fetches are not mocked). */
export async function mockApi(page: Page, overrides: { askStatus?: number; ask?: unknown } = {}) {
  await page.route(`${API}/v1/kpis/stream`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: `event: kpis\ndata: ${JSON.stringify(kpis)}\n\n`,
    }),
  );
  await page.route(`${API}/v1/kpis/live`, (route) => route.fulfill({ json: kpis }));
  await page.route(`${API}/v1/stations/live`, (route) => route.fulfill({ json: stations }));
  await page.route(`${API}/v1/stations/replay`, (route) =>
    route.fulfill({
      json: {
        hours: ["2026-11-07T19:00:00Z", "2026-11-07T20:00:00Z"],
        legend: {},
        stations: { a: "sb", b: "ff" },
      },
    }),
  );
  await page.route(`${API}/v1/ask`, (route) =>
    route.fulfill({
      status: overrides.askStatus ?? 200,
      json: overrides.ask ?? {
        question: "How many stations have no bikes right now?",
        status: "answered",
        answer: "142 stations have no bikes right now.",
        metrics: [
          {
            name: "empty_stations",
            definition: "In-service stations with no bike to rent right now.",
            unit: "",
          },
        ],
        query: { topic: "live", measures: ["empty_stations"] },
        rows: [{ empty_stations: 142 }],
        data_freshness_seconds: 64,
        suggestion: null,
        answer_source: "model",
        elapsed_ms: 1500,
      },
    }),
  );
}
