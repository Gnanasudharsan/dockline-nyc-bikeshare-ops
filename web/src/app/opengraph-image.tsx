import { ImageResponse } from "next/og";

export const alt = "Dockline: live operations intelligence for NYC bike share";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Deterministic dot field in the four state colors (no brand assets).
const COLORS = ["#E0701F", "#A9B3C1", "#2357C6", "#A9B3C1", "#A9B3C1", "#2357C6", "#E0701F"];

export default function OpenGraphImage() {
  const dots = Array.from({ length: 180 }, (_, index) => {
    const x = 640 + ((index * 97) % 520);
    const y = 60 + ((index * 53) % 510);
    return { x, y, color: COLORS[index % COLORS.length] ?? "#A9B3C1" };
  });
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        background: "#F6F7F9",
        position: "relative",
      }}
    >
      {dots.map((dot, index) => (
        <div
          key={index}
          style={{
            position: "absolute",
            left: dot.x,
            top: dot.y,
            width: 12,
            height: 12,
            borderRadius: 6,
            background: dot.color,
          }}
        />
      ))}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          padding: 72,
          width: 640,
          color: "#13202F",
        }}
      >
        <div style={{ fontSize: 76, fontWeight: 700, letterSpacing: -2 }}>Dockline</div>
        <div style={{ fontSize: 34, marginTop: 20, color: "#4A5A6E", lineHeight: 1.3 }}>
          Live operations intelligence for NYC bike share
        </div>
        <div style={{ fontSize: 22, marginTop: "auto", color: "#4A5A6E" }}>
          Independent project. Not affiliated with Citi Bike or Lyft.
        </div>
      </div>
    </div>,
    size,
  );
}
