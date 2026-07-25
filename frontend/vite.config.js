import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Proxy helper: forward API calls to FastAPI, but NOT browser page loads.
 *
 * Problem it solves: several API prefixes (/ai, /creative, /uploads) are ALSO
 * React Router page paths. A hard refresh on http://localhost:5173/creative
 * is a document request that would get proxied to the backend → 404.
 * Document requests send "Accept: text/html"; axios/fetch API calls don't.
 * bypass returning '/index.html' tells Vite to serve the SPA instead.
 * (Production doesn't need this — vercel.json rewrites all paths to index.html
 * and the API lives on a different origin.)
 */
const backend = {
  target: 'http://localhost:8000',
  bypass: (req) =>
    (req.headers.accept ?? '').includes('text/html') ? '/index.html' : null,
}

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth':      backend,
      '/stores':    backend,
      '/uploads':   backend,
      '/analytics': backend,
      '/ai':        backend,
      '/creative':  backend,
      '/transfers': backend,
      '/deals':     backend,
      '/customers': backend,
      '/static':    backend,
      '/reports':   backend,
    },
  },
})
