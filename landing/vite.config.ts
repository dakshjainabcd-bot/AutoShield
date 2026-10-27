import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'
import type { Plugin, Connect } from 'vite'

// Serve the sibling `web/` static build (dashboard, assets, media) under the
// same origin so that the landing-page "Explore Dashboard" link resolves.
function serveWeb(): Plugin {
  const webRoot = path.resolve(__dirname, '../web')

  return {
    name: 'serve-web-static',
    configureServer(server) {
      server.middlewares.use((req: Connect.IncomingMessage, res, next) => {
        const url = req.url ?? '/'

        // Only handle paths that should come from the web/ directory
        if (
          !url.startsWith('/dashboard') &&
          !url.startsWith('/assets') &&
          !url.startsWith('/media') &&
          !url.startsWith('/vendor')
        ) {
          return next()
        }

        // Strip query string
        const cleanUrl = url.split('?')[0]

        // Try exact file first, then index.html for directory routes
        const candidates = [
          path.join(webRoot, cleanUrl),
          path.join(webRoot, cleanUrl, 'index.html'),
        ]

        for (const candidate of candidates) {
          if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
            const ext = path.extname(candidate)
            const mimeTypes: Record<string, string> = {
              '.html': 'text/html; charset=utf-8',
              '.css': 'text/css',
              '.js': 'application/javascript',
              '.json': 'application/json',
              '.png': 'image/png',
              '.jpg': 'image/jpeg',
              '.jpeg': 'image/jpeg',
              '.svg': 'image/svg+xml',
              '.ico': 'image/x-icon',
              '.webp': 'image/webp',
              '.woff': 'font/woff',
              '.woff2': 'font/woff2',
              '.ttf': 'font/ttf',
              '.mp4': 'video/mp4',
              '.webm': 'video/webm',
              '.jsonl': 'application/x-ndjson',
            }
            res.setHeader('Content-Type', mimeTypes[ext] ?? 'application/octet-stream')
            fs.createReadStream(candidate).pipe(res)
            return
          }
        }

        next()
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), serveWeb()],
  server: {
    host: '127.0.0.1',
    port: 5220,
    strictPort: true,
  },
})
