import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      // SSE endpoints — rewrite to FastAPI so EventSource works same-origin with cookies
      { source: '/api/sse/tickets', destination: 'http://localhost:8000/sse/tickets' },
      { source: '/api/sse/:sessionId', destination: 'http://localhost:8000/sse/:sessionId' },
    ];
  },
};

export default nextConfig;
