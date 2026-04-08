type ApiErrorShape = {
    error?: string;
    detail?: string;
    message?: string;
};

export function getApiBaseUrl(): string {
    // In production, use /api proxy (same-origin) to avoid cross-domain cookie issues on mobile.
    // In development, also use /api since Next.js rewrites handle it.
    return '/api';
}

export function buildApiUrl(path: string): string {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${getApiBaseUrl()}${normalizedPath}`;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
    return fetch(buildApiUrl(path), {
        credentials: 'include',
        ...init,
    });
}

export async function getApiErrorMessage(response: Response, fallback: string): Promise<string> {
    try {
        const payload = (await response.json()) as ApiErrorShape | string;

        if (typeof payload === 'string' && payload.trim()) {
            return payload;
        }

        if (payload && typeof payload === 'object') {
            if (typeof payload.error === 'string' && payload.error.trim()) {
                return payload.error;
            }
            if (typeof payload.detail === 'string' && payload.detail.trim()) {
                return payload.detail;
            }
            if (typeof payload.message === 'string' && payload.message.trim()) {
                return payload.message;
            }
        }
    } catch {
        // Ignore parse errors and use fallback.
    }

    return fallback;
}
