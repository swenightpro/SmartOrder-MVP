import type { NextConfig } from "next";

const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      // SSE endpoints — rewrite to FastAPI so EventSource works same-origin with cookies
      { source: '/api/sse/tickets', destination: `${backendUrl}/sse/tickets` },
      { source: '/api/sse/:sessionId', destination: `${backendUrl}/sse/:sessionId` },
    ];
  },
};

export default nextConfig;
