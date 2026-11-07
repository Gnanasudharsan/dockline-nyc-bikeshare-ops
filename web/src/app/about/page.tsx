import type { Metadata } from "next";
import { REPO_URL } from "@/lib/api";

export const metadata: Metadata = {
  title: "About",
  description: "Who built Dockline, why, and where the data comes from.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-[760px] px-4 pt-10">
      <h1 className="headline text-3xl">About Dockline</h1>
      <div className="measure mt-6 space-y-4">
        <p>
          Bike share works only when a rider finds a bike where they start and a free dock where
          they finish. Dockline watches every station in New York City&apos;s bike share network,
          minute by minute, and turns the public feed into the numbers an operations team would
          need: where stations are empty or full right now, where trucks should go next, and which
          stations fail riders day after day.
        </p>
        <p>
          It was built by Gnanasudharsan Ashokumar as an end-to-end portfolio project: ingestion, a
          time-series warehouse, tested data models, a governed semantic layer, live dashboards, an
          analyst report, a language-model assistant that cannot invent numbers, and this site.
          Everything runs on free tiers and open-source software.
        </p>
        <p className="font-medium">
          Independent project. Not affiliated with Citi Bike or Lyft. Uses the public GBFS feed.
        </p>
      </div>

      <h2 className="headline mt-12 text-2xl">Data sources and licenses</h2>
      <ul className="measure mt-4 list-disc space-y-2 pl-5">
        <li>Station status and information: the operator&apos;s public GBFS feed.</li>
        <li>Weather: Open-Meteo (CC BY 4.0).</li>
        <li>
          Neighborhoods: NYC Department of City Planning, 2020 Neighborhood Tabulation Areas (NYC
          Open Data).
        </li>
        <li>Map tiles: OpenFreeMap, © OpenMapTiles, data © OpenStreetMap contributors.</li>
        <li>Dockline&apos;s own code: MIT license.</li>
      </ul>

      <h2 className="headline mt-12 text-2xl">Contact</h2>
      <p className="measure mt-4">
        Questions or ideas: open an issue on <a href={REPO_URL}>GitHub</a>.
      </p>
    </div>
  );
}
