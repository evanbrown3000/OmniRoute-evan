/** Preserve capture header values. Forwarding policy belongs to the transport. */
import type { IncomingHttpHeaders } from "node:http";

export function captureHeaders(
  headers: IncomingHttpHeaders | Record<string, string | string[] | undefined>
): Record<string, string> {
  return Object.fromEntries(Object.entries(headers)
    .filter((entry): entry is [string, string | string[]] => entry[1] !== undefined)
    .map(([name, value]) => [name, Array.isArray(value) ? value.join("\n") : value]));
}
