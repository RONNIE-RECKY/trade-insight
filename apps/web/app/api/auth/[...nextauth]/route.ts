import NextAuth from "next-auth";
import { authOptions } from "@/lib/auth";

// next-auth v4 predates Next 15/16's async route params: Next now hands the
// handler `{ params: Promise<...> }`, which v4 can't consume, and the route
// silently fails to register (every /api/auth/* call 404s and login can never
// establish a session). Awaiting params and passing a plain object through
// keeps v4 working until we migrate to Auth.js v5.
const handler = NextAuth(authOptions) as (
  req: Request,
  ctx: { params: { nextauth: string[] } }
) => Promise<Response>;

type RouteCtx = { params: Promise<{ nextauth: string[] }> };

export async function GET(req: Request, ctx: RouteCtx) {
  return handler(req, { params: await ctx.params });
}

export async function POST(req: Request, ctx: RouteCtx) {
  return handler(req, { params: await ctx.params });
}
