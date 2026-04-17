/**
 * Flatten fingerprint attributes for substring search (client-side).
 */
export function fingerprintSearchBlob(attrs: Record<string, unknown> | null | undefined): string {
  if (!attrs || typeof attrs !== "object") return "";
  const parts: string[] = [];
  const walk = (v: unknown): void => {
    if (v === null || v === undefined) return;
    if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
      parts.push(String(v));
      return;
    }
    if (Array.isArray(v)) {
      v.forEach(walk);
      return;
    }
    if (typeof v === "object") {
      Object.values(v as Record<string, unknown>).forEach(walk);
    }
  }
  walk(attrs);
  return parts.join(" ").toLowerCase();
}
