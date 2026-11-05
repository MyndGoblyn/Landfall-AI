const MANIFEST_PATH = "/catalog/manifest.json";
const RELEASE_PATH = /^\/catalog\/releases\/[0-9a-f]{64}\.json\.gz$/;
const SEMANTIC_MANIFEST_PATH = "/catalog/semantic/manifest.json";
const SEMANTIC_RELEASE_PATH =
  /^\/catalog\/semantic\/releases\/[0-9a-f]{64}\.json\.gz$/;

function objectKey(pathname: string): string | null {
  if (
    pathname === MANIFEST_PATH ||
    RELEASE_PATH.test(pathname) ||
    pathname === SEMANTIC_MANIFEST_PATH ||
    SEMANTIC_RELEASE_PATH.test(pathname)
  ) {
    return pathname.slice(1);
  }
  return null;
}

function responseHeaders(object: R2Object, pathname: string): Headers {
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("ETag", object.httpEtag);
  headers.set("Content-Length", String(object.size));
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Robots-Tag", "noindex, nofollow");
  headers.set(
    "Cache-Control",
    pathname === MANIFEST_PATH || pathname === SEMANTIC_MANIFEST_PATH
      ? "public, max-age=0, must-revalidate"
      : "public, max-age=31536000, immutable",
  );
  return headers;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const key = objectKey(url.pathname);
    if (key === null) {
      return new Response("Not Found", { status: 404 });
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", {
        status: 405,
        headers: { Allow: "GET, HEAD" },
      });
    }

    try {
      if (request.method === "HEAD") {
        const object = await env.CATALOG_BUCKET.head(key);
        if (object === null) {
          return new Response("Not Found", { status: 404 });
        }
        return new Response(null, {
          status: 200,
          headers: responseHeaders(object, url.pathname),
        });
      }

      const object = await env.CATALOG_BUCKET.get(key);
      if (object === null) {
        return new Response("Not Found", { status: 404 });
      }
      return new Response(object.body, {
        status: 200,
        headers: responseHeaders(object, url.pathname),
      });
    } catch (error) {
      console.error(
        JSON.stringify({
          message: "catalog object read failed",
          path: url.pathname,
          error: error instanceof Error ? error.message : String(error),
        }),
      );
      return new Response("Catalog temporarily unavailable", { status: 503 });
    }
  },
} satisfies ExportedHandler<Env>;
