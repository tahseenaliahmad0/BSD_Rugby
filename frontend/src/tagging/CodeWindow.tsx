/** The code window: big code buttons, then descriptors, players and a note for the current tag. */
import { Badge, Group, MultiSelect, Stack, Text, Textarea, Tooltip } from '@mantine/core';
import { useMemo, useState } from 'react';
import type { DescriptorGroup, Player, Tag, Template, TemplateButton } from '../api/types';
import { buttonForCode, groupsForButton, hasDescriptorValue } from './codeWindow';
import type { OpenSpan } from './store';
import { formatMs } from './time';

export interface CodeWindowProps {
  template: Template;
  players: Player[];
  openSpans: ReadonlyMap<string, OpenSpan>;
  targetTag: Tag | null;
  targetIsSelection: boolean;
  onPress: (button: TemplateButton) => void;
  onToggleDescriptor: (group: DescriptorGroup, value: string) => void;
  onSetPlayers: (playerIds: string[]) => void;
  onSetNote: (note: string | null) => void;
}

function keyLabel(key: string | null | undefined): string {
  if (!key) return '';
  return /^[A-Z]$/.test(key) ? `⇧${key}` : key;
}

export function CodeWindow(props: CodeWindowProps) {
  const { template, players, openSpans, targetTag, targetIsSelection, onPress, onToggleDescriptor, onSetPlayers, onSetNote } = props;
  const [note, setNote] = useState(targetTag?.note ?? '');
  const [noteSource, setNoteSource] = useState<string | null>(targetTag ? `${targetTag.id}:${targetTag.note ?? ''}` : null);
  const source = targetTag ? `${targetTag.id}:${targetTag.note ?? ''}` : null;
  if (source !== noteSource) {
    setNoteSource(source);
    setNote(targetTag?.note ?? '');
  }

  const playerOptions = useMemo(
    () =>
      [...players]
        .sort((a, b) => (a.shirt_number ?? 99) - (b.shirt_number ?? 99) || a.name.localeCompare(b.name))
        .map((p) => ({ value: p.id, label: p.shirt_number != null ? `${p.shirt_number}  ${p.name}` : p.name })),
    [players],
  );

  const button = targetTag ? buttonForCode(template, targetTag.code) : undefined;
  const groups = targetTag && button ? groupsForButton(template, button) : [];
  const optionGroups = groups.filter((g) => g.kind === 'options');
  const hasPlayers = groups.some((g) => g.kind === 'players');

  return (
    <Stack gap="md" data-testid="code-window">
      <div>
        <Text fw={700} mb={6}>
          {template.name}
        </Text>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(118px, 1fr))', gap: 8 }}>
          {template.buttons.map((b) => {
            const open = openSpans.has(b.code);
            return (
              <Tooltip key={b.code} label={b.kind === 'span' ? (open ? `Stop ${b.label || b.code}` : `Start ${b.label || b.code} (press again to stop)`) : `${b.label || b.code}: ${(b.lead_ms / 1000).toFixed(1)} s before to ${(b.lag_ms / 1000).toFixed(1)} s after`}>
                <button
                  type="button"
                  className={`code-button${open ? ' recording' : ''}`}
                  style={{ backgroundColor: b.colour }}
                  onClick={() => onPress(b)}
                  data-testid={`code-${b.code}`}
                  aria-pressed={open}
                >
                  <span>{b.label || b.code}</span>
                  <span className="hotkey">{open ? 'stop' : b.kind === 'span' ? `${keyLabel(b.hotkey)} ▶` : keyLabel(b.hotkey)}</span>
                </button>
              </Tooltip>
            );
          })}
        </div>
      </div>

      <div data-testid="tag-details">
        {targetTag ? (
          <Stack gap="sm">
            <Group gap="xs" align="center">
              <Badge size="lg" variant="filled" style={{ backgroundColor: button?.colour ?? '#868e96' }}>
                {button?.label || targetTag.code}
              </Badge>
              <Text size="sm" c="dimmed">
                {formatMs(targetTag.start_ms, true)} – {formatMs(targetTag.end_ms, true)}
              </Text>
              <Text size="xs" c="dimmed">
                {targetIsSelection ? 'selected' : 'latest tag'}
              </Text>
            </Group>
            {optionGroups.map((group) => (
              <div key={group.key}>
                <Text size="sm" fw={600} mb={4}>
                  {group.label}
                </Text>
                <Group gap={6}>
                  {group.options.map((o) => {
                    const on = hasDescriptorValue(targetTag.descriptors, group.key, o.value);
                    return (
                      <button
                        key={o.value}
                        type="button"
                        className={`chip-btn${on ? ' on' : ''}`}
                        onClick={() => onToggleDescriptor(group, o.value)}
                        aria-pressed={on}
                        data-testid={`descriptor-${group.key}-${o.value}`}
                      >
                        {o.label || o.value}
                        {o.hotkey && <span className="hotkey">{keyLabel(o.hotkey)}</span>}
                      </button>
                    );
                  })}
                </Group>
              </div>
            ))}
            {hasPlayers && (
              <MultiSelect
                label="Players"
                placeholder="Type a shirt number or name"
                searchable
                data={playerOptions}
                value={targetTag.player_ids}
                onChange={onSetPlayers}
                nothingFoundMessage="No player matches"
                comboboxProps={{ withinPortal: true }}
                data-testid="player-picker"
              />
            )}
            <Textarea
              label="Note"
              placeholder="Anything worth remembering"
              autosize
              minRows={1}
              value={note}
              onChange={(e) => setNote(e.currentTarget.value)}
              onBlur={() => {
                const trimmed = note.trim() || null;
                if (trimmed !== (targetTag.note ?? null)) onSetNote(trimmed);
              }}
              data-testid="tag-note"
            />
          </Stack>
        ) : (
          <Text c="dimmed" size="sm">
            Press a button or its key while the video plays. Details for the latest tag appear here.
          </Text>
        )}
      </div>
    </Stack>
  );
}
