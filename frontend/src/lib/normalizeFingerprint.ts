/**
 * Normalize fingerprint attribute keys/values from API (camelCase vs snake_case).
 */

export function normalizeAttributeKey(key: string): string {
  return key.replace(/([A-Z])/g, "_$1").toLowerCase();
}

const HEX = /^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})$/;

/** Extract hex colors from palette-like attribute values for swatches. */
export function extractPaletteColors(value: unknown): string[] {
  const out: string[] = [];
  const push = (raw: string) => {
    const t = raw.trim();
    const withHash = t.startsWith("#") ? t : `#${t}`;
    if (HEX.test(withHash)) out.push(withHash);
  };
  if (Array.isArray(value)) {
    for (const v of value) if (typeof v === "string") push(v);
  } else if (typeof value === "object" && value !== null) {
    for (const v of Object.values(value as Record<string, unknown>)) {
      if (typeof v === "string") push(v);
    }
  } else if (typeof value === "string") {
    const m = value.match(/#?[0-9a-fA-F]{6}\b|#?[0-9a-fA-F]{3}\b/g);
    if (m) m.forEach((x) => push(x.replace(/^#/, "")));
  }
  return [...new Set(out)].slice(0, 12);
}

export function isLikelyEnumValue(v: unknown): boolean {
  if (typeof v === "string") return true;
  if (typeof v === "object" && v !== null && "value" in (v as object)) return true;
  return false;
}

export function isContinuousFingerprintValue(v: unknown): boolean {
  if (typeof v === "number") return true;
  if (typeof v === "object" && v !== null) {
    const o = v as Record<string, unknown>;
    return (
      typeof o.score === "number" ||
      typeof o.mean === "number" ||
      typeof o.correlation === "number"
    );
  }
  return false;
}
