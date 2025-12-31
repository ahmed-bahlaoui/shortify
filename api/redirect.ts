/**
 * Vercel Edge Function for URL Redirection
 *
 * This edge function handles requests to short URL slugs (e.g., /r/g8)
 * and redirects to the original URL stored in Upstash Redis.
 */

export const config = {
  runtime: "edge",
};

// Upstash Redis REST API configuration
const UPSTASH_REDIS_REST_URL = process.env.UPSTASH_REDIS_REST_URL || "";
const UPSTASH_REDIS_REST_TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN || "";

/**
 * Fetch the original URL from Upstash Redis using REST API
 */
async function getOriginalUrl(slug: string): Promise<string | null> {
  try {
    const response = await fetch(
      `${UPSTASH_REDIS_REST_URL}/get/shortify:slug:${slug}`,
      {
        headers: {
          Authorization: `Bearer ${UPSTASH_REDIS_REST_TOKEN}`,
        },
      },
    );

    if (!response.ok) {
      console.error(`Redis error: ${response.status}`);
      return null;
    }

    const data = (await response.json()) as { result: string | null };
    return data.result || null;
  } catch (error) {
    console.error("Failed to fetch from Redis:", error);
    return null;
  }
}

export default async function handler(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const slug = url.searchParams.get("slug");

  if (!slug || !/^[a-zA-Z0-9]+$/.test(slug)) {
    return new Response("Invalid slug", { status: 400 });
  }

  const originalUrl = await getOriginalUrl(slug);

  if (originalUrl) {
    return Response.redirect(originalUrl, 307);
  }

  // Slug not found - redirect to home page
  return Response.redirect(new URL("/", request.url).toString(), 302);
}
