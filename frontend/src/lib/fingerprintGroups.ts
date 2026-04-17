/** Map fingerprint attribute keys to spec category groups. */

export type FingerprintGroup = "structural" | "visual" | "audio" | "content";

const VISUAL = new Set([
  "color_palette",
  "dominant_colors",
  "lighting_style",
  "composition",
  "visual_style",
  "aspect_ratio",
  "text_overlay_density",
  "brand_logo_visibility",
]);

const AUDIO = new Set([
  "music_genre",
  "voiceover_tone",
  "audio_energy",
  "has_voiceover",
  "sound_effects",
]);

const STRUCTURAL = new Set([
  "hook_type",
  "pacing",
  "scene_count",
  "duration_seconds",
  "cuts_per_minute",
  "format",
]);

export function fingerprintGroupForKey(key: string): FingerprintGroup {
  const k = key.toLowerCase();
  if (VISUAL.has(k) || k.includes("color") || k.includes("visual")) return "visual";
  if (AUDIO.has(k) || k.includes("audio") || k.includes("music") || k.includes("voice"))
    return "audio";
  if (STRUCTURAL.has(k) || k.includes("hook") || k.includes("pacing") || k.includes("duration"))
    return "structural";
  return "content";
}

export const GROUP_ORDER: FingerprintGroup[] = ["structural", "visual", "audio", "content"];

export const GROUP_LABELS: Record<FingerprintGroup, string> = {
  structural: "Structural",
  visual: "Visual",
  audio: "Audio",
  content: "Content",
};
