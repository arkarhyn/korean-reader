/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { readFileSync } from "node:fs";
import { networkInterfaces } from "node:os";
import { defineConfig, type ServerOptions } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// `npm run dev:phone`: hot-reloading dev server reachable from the iPhone over
// Tailscale. HTTPS is required (crypto.randomUUID in sync.ts needs a secure
// context), so it reuses the service's tailscale cert. /api goes to the live
// service on :8443, i.e. the phone sees and writes the real data.
// Listens on the Tailscale address only (100.64.0.0/10), not the home LAN;
// open it on the desktop via the same ts.net URL.
// Override with KR_CERT_DIR / KR_API.
function tailnetAddress(): string {
  for (const addrs of Object.values(networkInterfaces())) {
    for (const a of addrs ?? []) {
      const [o1, o2] = a.address.split(".").map(Number);
      if (a.family === "IPv4" && o1 === 100 && o2 >= 64 && o2 <= 127) return a.address;
    }
  }
  throw new Error("dev:phone: no Tailscale IPv4 address found -- is Tailscale up?");
}

function phoneServer(): ServerOptions {
  const certDir = process.env.KR_CERT_DIR ?? "C:/ProgramData/korean-reader/certs";
  const api = { target: process.env.KR_API ?? "https://127.0.0.1:8443", secure: false, changeOrigin: true };
  return {
    host: tailnetAddress(),
    port: 5173,
    strictPort: true,
    allowedHosts: [".ts.net"],
    https: { cert: readFileSync(`${certDir}/server.crt`), key: readFileSync(`${certDir}/server.key`) },
    proxy: { "/api": api, "/health": api },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["apple-touch-icon.png"],
      manifest: {
        name: "Korean Reader",
        short_name: "읽기",
        lang: "ko",
        start_url: "/",
        display: "standalone",
        background_color: "#f4ecd8",
        theme_color: "#f4ecd8",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // App shell is precached. Korean fonts are split into hundreds of
        // unicode-range slices, so only the slices actually used get cached.
        globPatterns: ["**/*.{js,css,html,png,webmanifest}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/health/],
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.destination === "font",
            handler: "CacheFirst",
            options: { cacheName: "fonts", expiration: { maxEntries: 800 } },
          },
        ],
      },
    }),
  ],
  server: mode === "phone" ? phoneServer() : { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: {
    environment: "jsdom",
  },
}));
