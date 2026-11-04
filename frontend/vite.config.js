import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In local development, forward /api requests to the FastAPI server on port 8000.
// On Vercel, /api is served by the Python function on the same domain.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
