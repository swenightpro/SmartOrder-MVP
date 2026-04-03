import type { NextConfig } from "next";

const backendUrl = process.env.INTERNAL_BACKEND_URL || 'http://localhost:8000';

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      { source: '/api/sse/tickets', destination: `${backendUrl}/sse/tickets` },
      { source: '/api/sse/:sessionId', destination: `${backendUrl}/sse/:sessionId` },
    ];
  },
};

export default nextConfig;
