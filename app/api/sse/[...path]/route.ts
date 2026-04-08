import { NextRequest } from 'next/server';

const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type RouteContext = {
    params: {
        path: string[];
    };
};

export async function GET(request: NextRequest, { params }: RouteContext) {
    const upstreamPath = Array.isArray(params.path) ? params.path.join('/') : '';
    const targetUrl = `${backendUrl}/sse/${upstreamPath}${request.nextUrl.search}`;

    const upstreamResponse = await fetch(targetUrl, {
        method: 'GET',
        headers: {
            Accept: 'text/event-stream',
            Cookie: request.headers.get('cookie') ?? '',
            'Cache-Control': 'no-cache',
            Connection: 'keep-alive',
        },
        cache: 'no-store',
        redirect: 'manual',
    });

    if (!upstreamResponse.body) {
        return new Response('Upstream SSE stream unavailable', { status: 502 });
    }

    const headers = new Headers(upstreamResponse.headers);
    headers.set('Content-Type', 'text/event-stream; charset=utf-8');
    headers.set('Cache-Control', 'no-cache, no-transform');
    headers.set('Connection', 'keep-alive');
    headers.set('X-Accel-Buffering', 'no');

    return new Response(upstreamResponse.body, {
        status: upstreamResponse.status,
        headers,
    });
}