"use client";

import { useEffect, useRef } from "react";
import type { Station } from "@/lib/types";

/**
 * A lightweight live map for small screens: every station drawn on a canvas in its
 * state color (offline as a ring), no basemap and no map library. It keeps the hero
 * fast on phones; the interactive MapLibre map loads only when asked for.
 */
export function DotMap({
  stations,
  label,
  className = "",
}: {
  stations: Station[];
  label: string;
  className?: string;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const element = canvas.current;
    if (!element || stations.length === 0) return;
    const draw = () => {
      const styles = getComputedStyle(document.documentElement);
      const color = (name: string) => styles.getPropertyValue(`--${name}`).trim();
      const ratio = window.devicePixelRatio || 1;
      const width = element.clientWidth;
      const height = element.clientHeight;
      element.width = Math.round(width * ratio);
      element.height = Math.round(height * ratio);
      const context = element.getContext("2d");
      if (!context) return;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      // Equirectangular projection corrected for latitude, fitted to the stations.
      const lats = stations.map((s) => s.latitude);
      const lons = stations.map((s) => s.longitude);
      const [minLat, maxLat] = [Math.min(...lats), Math.max(...lats)];
      const [minLon, maxLon] = [Math.min(...lons), Math.max(...lons)];
      const kx = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
      const spanX = (maxLon - minLon) * kx;
      const spanY = maxLat - minLat;
      const pad = 14;
      const scale = Math.min((width - 2 * pad) / spanX, (height - 2 * pad) / spanY);
      const offsetX = (width - spanX * scale) / 2;
      const offsetY = (height - spanY * scale) / 2;
      const radius = width < 420 ? 1.6 : 2.2;
      for (const station of stations) {
        const x = offsetX + (station.longitude - minLon) * kx * scale;
        const y = offsetY + (maxLat - station.latitude) * scale;
        context.beginPath();
        context.arc(x, y, radius, 0, Math.PI * 2);
        if (station.imbalance_state === "offline") {
          context.strokeStyle = color("offline");
          context.lineWidth = 1;
          context.stroke();
        } else {
          context.fillStyle = color(station.imbalance_state);
          context.fill();
        }
      }
    };
    draw();
    window.addEventListener("resize", draw);
    window.addEventListener("dockline-theme", draw);
    return () => {
      window.removeEventListener("resize", draw);
      window.removeEventListener("dockline-theme", draw);
    };
  }, [stations]);

  return (
    <canvas
      ref={canvas}
      role="img"
      aria-label={label}
      className={`block bg-surface ${className}`}
    />
  );
}
