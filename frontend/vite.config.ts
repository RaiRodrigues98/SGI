import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    // Servidor SSR customizado do SGI.
    server: { entry: "server" },
  },

  // Deploy self-hosted em Docker/Node.
  // Evita o preset Cloudflare usado pelo ambiente Lovable.
nitro: {
    preset: process.env.VERCEL ? "vercel" : "node-server",
  },
});
