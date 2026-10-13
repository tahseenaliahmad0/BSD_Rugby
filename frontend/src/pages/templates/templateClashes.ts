import type { TemplateContent } from '../../api/types';

export const PLAYER_KEYS = new Set([' ', ',', '.', 'j', 'k', 'l', 'f', 'm', 'J', 'K', 'L', 'F', 'M']);
export const COLOURS = ['#1971c2', '#e8590c', '#f08c00', '#9c36b5', '#2f9e44', '#868e96', '#0ca678', '#e03131', '#5c7cfa', '#c2255c', '#1098ad', '#fab005', '#d6336c', '#7950f2'];

export function keyLabel(key: string | null | undefined): string {
  if (!key) return '';
  return /^[A-Z]$/.test(key) ? `Shift+${key}` : key;
}

/** Local clash detection so problems show as you type, before the server confirms them. */
export function localClashes(content: TemplateContent): string[] {
  const owners = new Map<string, string[]>();
  for (const b of content.buttons) if (b.hotkey) owners.set(b.hotkey, [...(owners.get(b.hotkey) ?? []), b.label || b.code]);
  for (const g of content.descriptor_groups)
    for (const o of g.options) if (o.hotkey) owners.set(o.hotkey, [...(owners.get(o.hotkey) ?? []), `${g.label}: ${o.label || o.value}`]);
  const problems: string[] = [];
  for (const [key, names] of owners) {
    if (names.length > 1) problems.push(`'${key}' is used by ${names.join(', ')}`);
    if (PLAYER_KEYS.has(key)) problems.push(`'${key}' is used by the video player (${names.join(', ')})`);
  }
  const codes = content.buttons.map((b) => b.code.trim().toLowerCase());
  for (const code of new Set(codes)) if (code && codes.filter((c) => c === code).length > 1) problems.push(`Duplicate code '${code}'`);
  return problems;
}

