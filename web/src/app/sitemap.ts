import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/api";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "/live", "/ask", "/insights", "/how-it-works", "/about"].map((path) => ({
    url: `${SITE_URL}${path}`,
    changeFrequency: path === "" || path === "/live" ? "always" : "daily",
  }));
}
