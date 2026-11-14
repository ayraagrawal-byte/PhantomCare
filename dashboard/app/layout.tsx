import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PhantomCare",
  description: "Evidence-backed hospice registration review for Los Angeles County.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

