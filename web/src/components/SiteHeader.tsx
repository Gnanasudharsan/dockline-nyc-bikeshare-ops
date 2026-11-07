import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { href: "/live", label: "Live" },
  { href: "/ask", label: "Ask" },
  { href: "/insights", label: "Insights" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/about", label: "About" },
];

export function SiteHeader() {
  return (
    <header className="border-b border-line bg-paper">
      <a
        href="#main"
        className="sr-only min-h-6 focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:inline-flex focus:min-h-10 focus:items-center focus:bg-surface focus:px-3"
      >
        Skip to content
      </a>
      <div className="mx-auto grid max-w-[1200px] grid-cols-[1fr_auto] items-center gap-x-4 px-4 pt-2 md:grid-cols-[auto_1fr_auto] md:py-2">
        <Link
          href="/"
          className="headline col-start-1 row-start-1 py-1 text-lg text-ink no-underline"
        >
          Dockline
        </Link>
        <nav
          aria-label="Main"
          className="col-span-2 col-start-1 row-start-2 -mx-4 overflow-x-auto px-2 md:col-span-1 md:col-start-2 md:row-start-1 md:mx-0 md:justify-self-end md:px-0"
        >
          <ul className="flex whitespace-nowrap">
            {NAV.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="inline-flex min-h-10 items-center px-2 text-sm text-ink no-underline hover:text-signal"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="col-start-2 row-start-1 justify-self-end md:col-start-3">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
