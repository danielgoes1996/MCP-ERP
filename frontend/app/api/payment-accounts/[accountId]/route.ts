import { NextRequest } from 'next/server';
import { proxyRequest } from '../_proxy';

interface RouteParams {
  params: {
    accountId: string;
  };
}

export async function PUT(request: NextRequest, { params }: RouteParams) {
  const body = await request.text();
  return proxyRequest(request, `/payment-accounts/${params.accountId}`, {
    method: 'PUT',
    body,
    headers: {
      'content-type':
        request.headers.get('content-type') ?? 'application/json',
    },
  });
}

export async function DELETE(
  request: NextRequest,
  { params }: RouteParams
) {
  return proxyRequest(request, `/payment-accounts/${params.accountId}`, {
    method: 'DELETE',
  });
}
