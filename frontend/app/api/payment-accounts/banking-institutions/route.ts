import { NextRequest } from 'next/server';
import { proxyRequest } from '../_proxy';

export async function GET(request: NextRequest) {
  const search = request.nextUrl.search;
  return proxyRequest(
    request,
    `/payment-accounts/banking-institutions${search}`
  );
}
