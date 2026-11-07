import { REPO_URL } from "@/lib/api";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-line">
      <div className="mx-auto flex max-w-[1200px] flex-col gap-2 px-4 py-8 text-sm text-slate md:flex-row md:justify-between">
        <p className="measure">
          Independent project. Not affiliated with Citi Bike or Lyft. Uses the public GBFS feed.
        </p>
        <p>
          Station data: public GBFS feed · Weather: Open-Meteo · Map: OpenFreeMap, © OpenStreetMap
          contributors ·{" "}
          <a href={REPO_URL} rel="noopener">
            Source on GitHub
          </a>
        </p>
      </div>
    </footer>
  );
}
