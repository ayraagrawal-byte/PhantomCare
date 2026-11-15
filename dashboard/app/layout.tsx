import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Serif, Libre_Baskerville, Playfair_Display } from "next/font/google";
import "leaflet/dist/leaflet.css";
import "./globals.css";

const brand = Playfair_Display({ subsets: ["latin"], weight: "700", variable: "--font-brand", display: "swap" });
const headlines = Libre_Baskerville({ subsets: ["latin"], weight: "700", variable: "--font-headlines", display: "swap" });
const sections = IBM_Plex_Serif({ subsets: ["latin"], weight: "600", variable: "--font-sections", display: "swap" });
const body = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-body", display: "swap" });
const metadataFont = IBM_Plex_Mono({ subsets: ["latin"], weight: "500", variable: "--font-metadata", display: "swap" });

export const metadata: Metadata = {
  title: "PhantomCare",
  description: "Evidence-backed hospice registration review for Los Angeles County.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={[brand, headlines, sections, body, metadataFont].map(({ variable }) => variable).join(" ")}>
      <body>{children}</body>
    </html>
  );
}

