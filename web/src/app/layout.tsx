import type { Metadata, Viewport } from "next";
import { Archivo } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/SiteHeader";
import { SiteFooter } from "@/components/SiteFooter";
import { ThemeScript } from "@/components/ThemeScript";
import { SITE_URL } from "@/lib/api";

const archivo = Archivo({
  subsets: ["latin"],
  axes: ["wdth"],
  variable: "--font-archivo",
  display: "swap",
});

const description =
  "Live operations intelligence for NYC bike share: every station, every minute, with certified metrics and a governed Ask the Data.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "Dockline · live operations for NYC bike share", template: "%s · Dockline" },
  description,
  openGraph: {
    type: "website",
    siteName: "Dockline",
    title: "Dockline · live operations for NYC bike share",
    description,
    url: "/",
  },
  twitter: { card: "summary_large_image", title: "Dockline", description },
  alternates: { canonical: "/" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F6F7F9" },
    { media: "(prefers-color-scheme: dark)", color: "#0F1722" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={archivo.variable} suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body>
        <SiteHeader />
        <main id="main">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
