import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const allowedMethods = new Set(["GET", "POST", "PUT", "DELETE"]);
const forwardedHeaders = ["accept", "content-type", "cookie", "idempotency-key", "origin", "referer", "x-csrf-token", "x-request-id", "x-project-id"];

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (!allowedMethods.has(request.method)) {
    return NextResponse.json({ detail: "Method not allowed" }, { status: 405, headers: { Allow: "GET, POST, PUT, DELETE", "Cache-Control": "no-store" } });
  }

  const configured = process.env.BACKEND_URL;
  if (!configured) return NextResponse.json({ detail: "Backend is not configured" }, { status: 503, headers: { "Cache-Control": "no-store" } });

  let backend: URL;
  try {
    backend = new URL(configured);
    if (!["http:", "https:"].includes(backend.protocol) || backend.username || backend.password) throw new Error("Invalid backend URL");
  } catch {
    return NextResponse.json({ detail: "Backend configuration is invalid" }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }

  const { path } = await context.params;
  const suffix = path.map((part) => encodeURIComponent(part)).join("/");
  const mutating = request.method !== "GET";
  // Next standalone may normalize nextUrl's hostname to localhost inside the
  // container. Use the incoming Host authority, while retaining its URL scheme.
  const authority = request.headers.get("host");
  const expectedOrigin = authority ? `${request.nextUrl.protocol}//${authority}` : null;
  if (mutating && request.headers.get("origin") !== expectedOrigin) {
    return NextResponse.json({ detail: "Request origin is not allowed" }, { status: 403, headers: { "Cache-Control": "no-store" } });
  }
  if (mutating && suffix !== "auth/login" && !request.headers.get("x-csrf-token")) {
    return NextResponse.json({ detail: "CSRF token is required" }, { status: 403, headers: { "Cache-Control": "no-store" } });
  }
  const target = new URL(`/api/v1/${suffix}`, backend);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  for (const name of forwardedHeaders) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("accept", request.headers.get("accept") ?? "application/json");

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(30_000),
    });
    const responseHeaders = new Headers();
    for (const name of ["content-type", "location", "retry-after", "www-authenticate", "x-request-id"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    responseHeaders.set("Cache-Control", "no-store, private");
    const getSetCookie = upstream.headers.getSetCookie?.bind(upstream.headers);
    for (const cookie of getSetCookie ? getSetCookie() : []) responseHeaders.append("Set-Cookie", cookie);
    return new NextResponse(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return NextResponse.json({ detail: "The platform API is temporarily unavailable" }, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
export const PUT = proxy;
