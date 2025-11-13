import { NextRequest, NextResponse } from 'next/server';

const backendBase =
  process.env.FINANCE_API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_FINANCE_API_URL ??
  'http://localhost:8001';

const sanitizedBase = backendBase.replace(/\/$/, '');

export async function proxyRequest(
  request: NextRequest,
  targetPath: string,
  init?: RequestInit
) {
  const absoluteUrl = targetPath.startsWith('http')
    ? targetPath
    : `${sanitizedBase}${targetPath}`;

  const headers = new Headers(init?.headers);
  const incomingHeaders = request.headers;

  const authHeader = incomingHeaders.get('authorization');
  if (authHeader && !headers.has('authorization')) {
    headers.set('authorization', authHeader);
  }

  const cookieHeader = incomingHeaders.get('cookie');
  if (cookieHeader && !headers.has('cookie')) {
    headers.set('cookie', cookieHeader);
  }

  if (!headers.has('content-type')) {
    const contentType = incomingHeaders.get('content-type');
    if (contentType) {
      headers.set('content-type', contentType);
    }
  }

  const response = await fetch(absoluteUrl, {
    ...init,
    headers,
    cache: 'no-store',
    redirect: 'manual',
  });

  const nextHeaders = new Headers();
  const contentType = response.headers.get('content-type');
  if (contentType) {
    nextHeaders.set('content-type', contentType);
  }

  if (response.headers.has('set-cookie')) {
    nextHeaders.append('set-cookie', response.headers.get('set-cookie') as string);
  }

  return new NextResponse(response.body, {
    status: response.status,
    headers: nextHeaders,
  });
}
