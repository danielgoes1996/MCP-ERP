import { NextRequest } from 'next/server';
import { proxyRequest } from './_proxy';

export async function GET(request: NextRequest) {
  const search = request.nextUrl.search;
  return proxyRequest(request, `/payment-accounts${search}`);
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyRequest(request, '/payment-accounts', {
    method: 'POST',
    body,
    headers: {
      'content-type':
        request.headers.get('content-type') ?? 'application/json',
    },
  });
}
