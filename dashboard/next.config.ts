import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Playwright and the loopback API use 127.0.0.1; Next.js 16 otherwise blocks
  // dev-only resources (HMR, client chunks) for that origin and the page never
  // hydrates. This setting has no effect on production builds.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
