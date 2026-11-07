"use client";

import { useSyncExternalStore } from "react";

type Theme = "light" | "dark";

function currentTheme(): Theme {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit === "light" || explicit === "dark") return explicit;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  window.addEventListener("dockline-theme", onChange);
  media.addEventListener("change", onChange);
  return () => {
    window.removeEventListener("dockline-theme", onChange);
    media.removeEventListener("change", onChange);
  };
}

/** Switches between light and dark; the label says what the button will do. */
export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, currentTheme, () => null);
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      onClick={() => {
        document.documentElement.setAttribute("data-theme", next);
        try {
          localStorage.setItem("dockline-theme", next);
        } catch {
          /* storage unavailable: the choice lasts for this page only */
        }
        window.dispatchEvent(new CustomEvent("dockline-theme", { detail: next }));
      }}
      className="min-h-9 rounded px-3 text-sm text-slate hover:text-ink"
      aria-label={theme ? `Switch to ${next} theme` : "Switch theme"}
    >
      {theme ? `${next === "dark" ? "Dark" : "Light"} theme` : "Theme"}
    </button>
  );
}
