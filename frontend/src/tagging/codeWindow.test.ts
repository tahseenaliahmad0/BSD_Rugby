import { describe, expect, it } from 'vitest';
import type { DescriptorGroup, Template, TemplateButton } from '../api/types';
import {
  closeSpanEnd,
  findButton,
  findOption,
  groupsForButton,
  hasDescriptorValue,
  hotkeyFromEvent,
  instantRange,
  MIN_SPAN_MS,
  OPEN_SPAN_PLACEHOLDER_MS,
  openSpanRange,
  toggleDescriptor,
} from './codeWindow';

const tackle: TemplateButton = { code: 'Tackle', hotkey: 't', colour: '#5c7cfa', kind: 'instant', lead_ms: 3000, lag_ms: 2000, groups: ['tackle', 'players'] };
const scrum: TemplateButton = { code: 'Scrum', hotkey: '2', colour: '#e8590c', kind: 'span', lead_ms: 0, lag_ms: 0, groups: ['outcome'] };
const outcome: DescriptorGroup = { key: 'outcome', label: 'Outcome', kind: 'options', multiple: false, options: [{ value: 'Won', hotkey: 'A' }, { value: 'Lost', hotkey: 'S' }] };
const zone: DescriptorGroup = { key: 'zone', label: 'Zone', kind: 'options', multiple: true, options: [{ value: 'Own 22', hotkey: 'Q' }, { value: 'Opp 22', hotkey: 'R' }] };
const players: DescriptorGroup = { key: 'players', label: 'Players', kind: 'players', multiple: true, options: [] };
const tackleGroup: DescriptorGroup = { key: 'tackle', label: 'Tackle', kind: 'options', multiple: false, options: [{ value: 'Made', hotkey: 'D' }] };
const template: Template = {
  id: 't1', squad_id: 's', family_id: 'f', name: 'Test', version: 1, is_active: true, created_by: null, created_at: '',
  buttons: [tackle, scrum], descriptor_groups: [outcome, zone, players, tackleGroup], outcome_group: 'outcome', success_values: ['Won'],
};

describe('instant codes apply lead and lag', () => {
  it('surrounds the press time', () => {
    expect(instantRange(tackle, 60_000)).toEqual({ start_ms: 57_000, end_ms: 62_000 });
  });
  it('never starts before zero or ends after the video', () => {
    expect(instantRange(tackle, 1_000)).toEqual({ start_ms: 0, end_ms: 3_000 });
    expect(instantRange(tackle, 99_000, 100_000)).toEqual({ start_ms: 96_000, end_ms: 100_000 });
  });
  it('keeps a minimum length when lead and lag are zero', () => {
    expect(instantRange(scrum, 10_000)).toEqual({ start_ms: 10_000, end_ms: 10_000 + MIN_SPAN_MS });
  });
  it('rounds fractional milliseconds', () => {
    expect(instantRange(tackle, 1234.6)).toEqual({ start_ms: 0, end_ms: 3235 });
  });
});

describe('start/stop codes', () => {
  it('open with a visible placeholder and close at the second press', () => {
    expect(openSpanRange(5_000)).toEqual({ start_ms: 5_000, end_ms: 5_000 + OPEN_SPAN_PLACEHOLDER_MS });
    expect(closeSpanEnd(5_000, 12_345)).toBe(12_345);
  });
  it('cannot close before the start', () => {
    expect(closeSpanEnd(5_000, 4_000)).toBe(5_000 + MIN_SPAN_MS);
    expect(closeSpanEnd(5_000, 5_100)).toBe(5_000 + MIN_SPAN_MS);
  });
});

describe('descriptors', () => {
  it('single-value groups set, replace and clear', () => {
    let d = toggleDescriptor({}, outcome, 'Won');
    expect(d).toEqual({ outcome: 'Won' });
    d = toggleDescriptor(d, outcome, 'Lost');
    expect(d).toEqual({ outcome: 'Lost' });
    d = toggleDescriptor(d, outcome, 'Lost');
    expect(d).toEqual({});
  });
  it('multi-value groups accumulate and remove', () => {
    let d = toggleDescriptor({ outcome: 'Won' }, zone, 'Own 22');
    d = toggleDescriptor(d, zone, 'Opp 22');
    expect(d).toEqual({ outcome: 'Won', zone: ['Own 22', 'Opp 22'] });
    d = toggleDescriptor(d, zone, 'Own 22');
    expect(d).toEqual({ outcome: 'Won', zone: ['Opp 22'] });
    d = toggleDescriptor(d, zone, 'Opp 22');
    expect(d).toEqual({ outcome: 'Won' });
    expect(hasDescriptorValue({ zone: ['Opp 22'] }, 'zone', 'Opp 22')).toBe(true);
    expect(hasDescriptorValue({ zone: 'Opp 22' }, 'zone', 'Own 22')).toBe(false);
  });
  it('does not mutate the input', () => {
    const original = { outcome: 'Won' };
    toggleDescriptor(original, outcome, 'Lost');
    expect(original).toEqual({ outcome: 'Won' });
  });
});

describe('hotkeys', () => {
  it('ignores modifier shortcuts and non-character keys', () => {
    expect(hotkeyFromEvent({ key: 'z', ctrlKey: true, metaKey: false, altKey: false })).toBeNull();
    expect(hotkeyFromEvent({ key: 'ArrowLeft', ctrlKey: false, metaKey: false, altKey: false })).toBeNull();
    expect(hotkeyFromEvent({ key: 't', ctrlKey: false, metaKey: false, altKey: false })).toBe('t');
    expect(hotkeyFromEvent({ key: 'A', ctrlKey: false, metaKey: false, altKey: false })).toBe('A');
  });
  it('finds buttons and options by key, case-sensitively', () => {
    expect(findButton(template, 't')?.code).toBe('Tackle');
    expect(findButton(template, 'T')).toBeUndefined();
    expect(findOption(template, 'A')?.option.value).toBe('Won');
    expect(findOption(template, 'R')?.group.key).toBe('zone');
    expect(findOption(template, 'a')).toBeUndefined();
  });
  it('lists a button\'s groups with players last', () => {
    expect(groupsForButton(template, tackle).map((g) => g.key)).toEqual(['tackle', 'players']);
    expect(groupsForButton(template, scrum).map((g) => g.key)).toEqual(['outcome']);
  });
});
