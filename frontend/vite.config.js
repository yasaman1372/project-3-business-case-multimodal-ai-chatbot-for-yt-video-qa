import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In local development, forward /api requests to the FastAPI server
// (port 8000 by default; override with API_URL=http://localhost:8001 npm run dev).
// On Vercel, /api is served by the Python function on the same domain.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": process.env.API_URL || "http://localhost:8000",
    },
  },
});
