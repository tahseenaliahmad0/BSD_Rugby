import type { Clip, Tag } from '../api/types';

/** Plain words for a clip: "Lineout · Lost · Opp 22" (plus the note when there is one). */
export function descriptorWords(tag: Tag | null): string[] {
  if (!tag) return [];
  const words: string[] = [];
  for (const value of Object.values(tag.descriptors)) {
    if (Array.isArray(value)) words.push(...value);
    else if (value) words.push(value);
  }
  return words;
}

export function clipTitle(clip: Clip): string {
  const parts = [clip.label, ...descriptorWords(clip.tag)];
  return parts.join(' · ');
}

export function clipDurationS(clip: Clip): number {
  return Math.max(0, (clip.end_ms - clip.start_ms) / 1000);
}
