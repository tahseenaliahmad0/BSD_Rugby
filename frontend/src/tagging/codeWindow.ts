/**
 * Pure logic for the code window: what a button press or a hotkey does.
 *
 * Instant codes make a tag around the current time using the button's lead and lag.
 * Span (start/stop) codes open a tag on the first press and close it on the second.
 * Descriptor options toggle values on a tag. Hotkeys are single characters; Shift makes the
 * upper-case variant, which is how option hotkeys stay distinct from button hotkeys.
 */
import type { DescriptorGroup, DescriptorOption, Descriptors, Template, TemplateButton } from '../api/types';

/** Minimum length of a span that is closed at (or before) its own start. */
export const MIN_SPAN_MS = 500;
/** Placeholder length given to a span the moment it opens, so it exists on the server. */
export const OPEN_SPAN_PLACEHOLDER_MS = 1000;

export interface TagRange {
  start_ms: number;
  end_ms: number;
}

/** The tag range for an instant press at `nowMs`, clamped to [0, durationMs]. */
export function instantRange(button: TemplateButton, nowMs: number, durationMs?: number): TagRange {
  const start = Math.max(0, nowMs - button.lead_ms);
  let end = nowMs + button.lag_ms;
  if (durationMs !== undefined && durationMs > 0) end = Math.min(end, durationMs);
  if (end <= start) end = start + MIN_SPAN_MS;
  return { start_ms: Math.round(start), end_ms: Math.round(end) };
}

/** The range an opening span gets so that it is visible immediately. */
export function openSpanRange(nowMs: number): TagRange {
  const start = Math.max(0, Math.round(nowMs));
  return { start_ms: start, end_ms: start + OPEN_SPAN_PLACEHOLDER_MS };
}

/** The end time for a span closed at `nowMs`; never shorter than MIN_SPAN_MS. */
export function closeSpanEnd(startMs: number, nowMs: number): number {
  return Math.max(Math.round(nowMs), startMs + MIN_SPAN_MS);
}

/** Toggle an option on a tag's descriptors; single-value groups replace, multi groups accumulate. */
export function toggleDescriptor(
  descriptors: Descriptors,
  group: DescriptorGroup,
  value: string,
): Descriptors {
  const next: Descriptors = { ...descriptors };
  const current = next[group.key];
  if (group.multiple) {
    const list = Array.isArray(current) ? [...current] : current ? [current] : [];
    const index = list.indexOf(value);
    if (index >= 0) list.splice(index, 1);
    else list.push(value);
    if (list.length === 0) delete next[group.key];
    else next[group.key] = list;
  } else if (current === value) {
    delete next[group.key];
  } else {
    next[group.key] = value;
  }
  return next;
}

export function hasDescriptorValue(descriptors: Descriptors, key: string, value: string): boolean {
  const current = descriptors[key];
  return Array.isArray(current) ? current.includes(value) : current === value;
}

/** The hotkey character for a key event, or null when modifiers make it a shortcut instead. */
export function hotkeyFromEvent(event: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'metaKey' | 'altKey'>): string | null {
  if (event.ctrlKey || event.metaKey || event.altKey) return null;
  if (event.key.length !== 1) return null;
  return event.key;
}

export function findButton(template: Template, key: string): TemplateButton | undefined {
  return template.buttons.find((b) => b.hotkey === key);
}

export function findOption(
  template: Template,
  key: string,
): { group: DescriptorGroup; option: DescriptorOption } | undefined {
  for (const group of template.descriptor_groups) {
    const option = group.options.find((o) => o.hotkey === key);
    if (option) return { group, option };
  }
  return undefined;
}

/** Groups a button offers, in template order; players groups come last. */
export function groupsForButton(template: Template, button: TemplateButton): DescriptorGroup[] {
  const groups = button.groups
    .map((key) => template.descriptor_groups.find((g) => g.key === key))
    .filter((g): g is DescriptorGroup => g !== undefined);
  return [...groups.filter((g) => g.kind !== 'players'), ...groups.filter((g) => g.kind === 'players')];
}

export function buttonForCode(template: Template | null | undefined, code: string): TemplateButton | undefined {
  return template?.buttons.find((b) => b.code === code);
}

/** Stable, readable colour for a code that is not in the template. */
export function fallbackColour(code: string): string {
  let hash = 0;
  for (const ch of code) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = hash % 360;
  return `hsl(${hue} 55% 42%)`;
}
