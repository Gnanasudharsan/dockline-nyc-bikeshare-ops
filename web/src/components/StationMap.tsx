"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef } from "react";
import type {
  DataDrivenPropertyValueSpecification,
  ExpressionSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
  MapLayerMouseEvent,
  Popup,
} from "maplibre-gl";
import type { ImbalanceState, Station } from "@/lib/types";
import { formatInt } from "@/lib/format";

const STYLE_LIGHT = "https://tiles.openfreemap.org/styles/positron";
const STYLE_DARK = "https://tiles.openfreemap.org/styles/dark";
const LABELS: Record<ImbalanceState, string> = {
  starving: "Starving (few or no bikes)",
  balanced: "Balanced",
  flooding: "Flooding (few or no docks)",
  offline: "Offline (not in service)",
};

function isDark(): boolean {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit) return explicit === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
}

function toGeoJson(stations: Station[], states?: Record<string, ImbalanceState | null>) {
  return {
    type: "FeatureCollection" as const,
    features: stations
      .map((station) => {
        const state = states ? states[station.station_id] : station.imbalance_state;
        if (!state) return null;
        return {
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [station.longitude, station.latitude] },
          properties: {
            name: station.station_name,
            state,
            bikes: states ? null : station.station_bikes_available,
            docks: states ? null : station.station_docks_available,
          },
        };
      })
      .filter((feature) => feature !== null),
  };
}

interface Props {
  stations: Station[];
  /** Override each station's state (replay frames). Missing = hidden. */
  states?: Record<string, ImbalanceState | null>;
  /** Accessible name for the map region. */
  label: string;
  className?: string;
  initialZoom?: number;
  /** Pixels of map covered by an overlay on wide screens (left edge). */
  overlayLeft?: number;
}

/**
 * Station dots on an OpenFreeMap basemap, colored by imbalance state.
 * Offline stations are hollow rings, so state is readable without color.
 * Stations fade in once on first load (skipped with prefers-reduced-motion).
 */
export function StationMap({
  stations,
  states,
  label,
  className = "",
  initialZoom,
  overlayLeft = 0,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const data = useMemo(() => toGeoJson(stations, states), [stations, states]);
  const dataRef = useRef(data);

  useEffect(() => {
    let cancelled = false;
    let popup: Popup | undefined;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    async function init() {
      const maplibregl = await import("maplibre-gl");
      if (cancelled || !container.current) return;
      const narrow = container.current.clientWidth < 640;
      const map = new maplibregl.Map({
        container: container.current,
        style: isDark() ? STYLE_DARK : STYLE_LIGHT,
        center: [-73.955, 40.735],
        zoom: initialZoom ?? (narrow ? 10.2 : 11.3),
        minZoom: 9,
        maxZoom: 17,
        attributionControl: { compact: true },
        cooperativeGestures: narrow,
      });
      mapRef.current = map;
      // Keep the visual center clear of an overlay, but only where there is room for it.
      const applyPadding = () => {
        const width = map.getContainer().clientWidth;
        const left = width >= 1100 ? Math.min(overlayLeft, width * 0.45) : 0;
        map.setPadding({ top: 0, right: 0, bottom: 0, left });
      };
      if (overlayLeft > 0) {
        applyPadding();
        map.on("resize", applyPadding);
      }
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });

      const addLayers = () => {
        const colors: ExpressionSpecification = [
          "match",
          ["get", "state"],
          "starving",
          token("starving"),
          "flooding",
          token("flooding"),
          "offline",
          token("offline"),
          token("balanced"),
        ];
        if (!map.getSource("stations")) {
          map.addSource("stations", { type: "geojson", data: dataRef.current });
        }
        const radius: DataDrivenPropertyValueSpecification<number> = [
          "interpolate",
          ["linear"],
          ["zoom"],
          9,
          1.6,
          12,
          3.2,
          15,
          6.5,
        ];
        map.addLayer({
          id: "stations-filled",
          type: "circle",
          source: "stations",
          filter: ["!=", ["get", "state"], "offline"],
          paint: {
            "circle-color": colors,
            "circle-radius": radius,
            "circle-stroke-width": 0.6,
            "circle-stroke-color": token("surface"),
            "circle-opacity": reduceMotion ? 0.92 : 0,
            "circle-opacity-transition": { duration: reduceMotion ? 0 : 600 },
          },
        });
        map.addLayer({
          id: "stations-offline",
          type: "circle",
          source: "stations",
          filter: ["==", ["get", "state"], "offline"],
          paint: {
            "circle-radius": radius,
            "circle-color": "rgba(0,0,0,0)",
            "circle-stroke-width": 1.4,
            "circle-stroke-color": token("offline"),
            "circle-opacity": reduceMotion ? 1 : 0,
            "circle-stroke-opacity": reduceMotion ? 1 : 0,
            "circle-stroke-opacity-transition": { duration: reduceMotion ? 0 : 600 },
          },
        });
        if (!reduceMotion) {
          requestAnimationFrame(() => {
            map.setPaintProperty("stations-filled", "circle-opacity", 0.92);
            map.setPaintProperty("stations-offline", "circle-stroke-opacity", 1);
          });
        }
      };

      map.on("load", addLayers);

      for (const layer of ["stations-filled", "stations-offline"]) {
        map.on("mousemove", layer, (event: MapLayerMouseEvent) => {
          const feature = event.features?.[0];
          if (!feature || !popup) return;
          map.getCanvas().style.cursor = "pointer";
          const props = feature.properties as {
            name: string;
            state: ImbalanceState;
            bikes: number | null;
            docks: number | null;
          };
          const counts =
            props.bikes === null || props.bikes === undefined
              ? ""
              : `<br>${formatInt(props.bikes)} bikes · ${formatInt(props.docks)} docks`;
          const element = document.createElement("div");
          element.className = "text-sm";
          element.innerHTML = `<strong></strong><br><span></span>${counts}`;
          (element.querySelector("strong") as HTMLElement).textContent = props.name;
          (element.querySelector("span") as HTMLElement).textContent = LABELS[props.state];
          popup.setLngLat(event.lngLat).setDOMContent(element).addTo(map);
        });
        map.on("mouseleave", layer, () => {
          map.getCanvas().style.cursor = "";
          popup?.remove();
        });
      }

      const onTheme = () => {
        map.setStyle(isDark() ? STYLE_DARK : STYLE_LIGHT);
        map.once("style.load", addLayers);
      };
      window.addEventListener("dockline-theme", onTheme);
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      media.addEventListener("change", onTheme);
      map.once("remove", () => {
        window.removeEventListener("dockline-theme", onTheme);
        media.removeEventListener("change", onTheme);
      });
    }

    void init();
    return () => {
      cancelled = true;
      popup?.remove();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [initialZoom, overlayLeft]);

  useEffect(() => {
    dataRef.current = data;
    const source = mapRef.current?.getSource("stations") as GeoJSONSource | undefined;
    source?.setData(data);
  }, [data]);

  return (
    <div
      ref={container}
      role="region"
      aria-label={label}
      className={`relative overflow-hidden bg-surface ${className}`}
    />
  );
}
