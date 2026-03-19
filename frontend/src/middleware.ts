import { Auth0Client } from "@auth0/nextjs-auth0/server";

export const auth0 = new Auth0Client({
  authorizationParameters: process.env.AUTH0_AUDIENCE
    ? { audience: process.env.AUTH0_AUDIENCE }
    : undefined,
});

export async function middleware(request: Request) {
  return await auth0.middleware(request);
}

export const config = {
  matcher: [
    // Auth routes
    "/auth/:path*",
    // Protected routes
    "/chat/:path*",
    "/profile/:path*",
  ],
};
