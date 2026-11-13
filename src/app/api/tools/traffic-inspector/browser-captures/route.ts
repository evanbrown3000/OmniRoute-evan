/** Authenticated server-to-server relay to the existing Accounts capture owner. */
export async function POST(request: Request): Promise<Response> {
  const key = process.env.NATIVE_CORE_CAPTURE_KEY;
  if (!key) return Response.json({ error: "Accounts capture connection is not configured" }, { status: 503 });
  const endpoint = process.env.ACCOUNTS_CAPTURE_URL ||
    "https://cognilode.com/api/native-core/capture/browser-captures";
  const response = await fetch(endpoint, {
    method: "POST", body: request.body, redirect: "error", cache: "no-store",
    headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
    duplex: "half", signal: request.signal,
  } as RequestInit & { duplex: "half" });
  return new Response(response.body, { status: response.status,
    headers: { "content-type": "application/json", "cache-control": "no-store, private" } });
}
