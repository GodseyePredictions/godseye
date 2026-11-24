import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "/nfl", "/nba", "/responsible-gambling", "/terms", "/privacy", "/contact"].map((path) => ({
    url: `${SITE.url}${path}`,
    changeFrequency: path === "" || path === "/nfl" || path === "/nba" ? "daily" : "yearly",
    priority: path === "" ? 1 : 0.6,
  }));
}
