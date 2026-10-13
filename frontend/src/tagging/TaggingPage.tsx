/** The analyst workspace: player on top, code window beside it, timeline below. */
import { ActionIcon, Alert, Button, Group, Kbd, Loader, Paper, Popover, Select, Stack, Table, Text, Title, Tooltip } from '@mantine/core';
import {
  IconAlertCircle,
  IconArrowBackUp,
  IconArrowForwardUp,
  IconArrowLeft,
  IconArrowsJoin,
  IconCut,
  IconKeyboard,
  IconTrash,
} from '@tabler/icons-react';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { Link, useParams } from 'react-router';
import { useEvent } from '../api/hooks';
import { usePlayers, useTemplates } from '../api/hooksM2';
import type { DescriptorGroup, Template, TemplateButton } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { VideoPlayer, type PlayerHandle } from '../player/VideoPlayer';
import { CodeWindow } from './CodeWindow';
import {
  buttonForCode,
  closeSpanEnd,
  fallbackColour,
  findButton,
  findOption,
  hotkeyFromEvent,
  instantRange,
  openSpanRange,
  toggleDescriptor,
} from './codeWindow';
import { TagStore } from './store';
import { httpTagApi } from './tagApi';
import { Timeline, type TimelineRow } from './Timeline';
import { eventMsToVideoSeconds, snapEventMsToFrame, videoSecondsToEventMs } from './time';

const SHORTCUTS: Array<[string, string]> = [
  ['Letter or digit', 'Press a code button (shown on each button)'],
  ['Shift + letter', 'Set a descriptor on the latest or selected tag'],
  ['Cmd/Ctrl + Z', 'Undo'],
  ['Shift + Cmd/Ctrl + Z, Ctrl + Y', 'Redo'],
  ['Alt + S', 'Split the selected tag at the playhead'],
  ['Alt + M', 'Merge the selected tags'],
  ['Delete / Backspace', 'Delete the selected tags'],
  ['Esc', 'Clear the selection'],
  ['Space, J, K, L, arrows', 'Player controls (see the player help)'],
];

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

export function TaggingPage() {
  const { eventId = '' } = useParams();
  const { canEdit } = useAuth();
  const { data: event, isPending } = useEvent(eventId);
  const squadId = event?.squad_id ?? '';
  const { data: templates } = useTemplates(squadId);
  const { data: players } = usePlayers(squadId);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);

  const store = useMemo(() => new TagStore(eventId, httpTagApi), [eventId]);
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot);
  useEffect(() => {
    void store.load();
  }, [store]);

  const video = event?.videos.find((v) => v.status === 'ready') ?? null;
  const fps = useMemo(() => ({ num: video?.fps_num ?? 30, den: video?.fps_den ?? 1 }), [video?.fps_num, video?.fps_den]);
  const offsetMs = video?.offset_ms ?? 0;
  const durationMs = Math.round((video?.duration_s ?? 0) * 1000);
  const endMs = offsetMs + durationMs;

  const template: Template | null = useMemo(() => {
    if (!templates || templates.length === 0) return null;
    return templates.find((t) => t.id === templateId) ?? templates.find((t) => t.name.includes('15s')) ?? templates[0];
  }, [templateId, templates]);

  const playerRef = useRef<PlayerHandle>(null);
  const [playheadMs, setPlayheadMs] = useState(offsetMs);
  const [playing, setPlaying] = useState(false);
  const onTime = useCallback(
    (seconds: number) => {
      setPlayheadMs(videoSecondsToEventMs(seconds, offsetMs));
      setPlaying(!(playerRef.current?.isPaused() ?? true));
    },
    [offsetMs],
  );

  const nowMs = useCallback(() => {
    const t = playerRef.current?.getTime() ?? 0;
    return snapEventMsToFrame(videoSecondsToEventMs(t, offsetMs), offsetMs, fps);
  }, [fps, offsetMs]);

  const seekToMs = useCallback((ms: number) => playerRef.current?.seek(eventMsToVideoSeconds(ms, offsetMs)), [offsetMs]);

  // Code presses ---------------------------------------------------------------------------
  const press = useCallback(
    (button: TemplateButton) => {
      if (!template) return;
      const now = nowMs();
      if (button.kind === 'span') {
        if (store.isOpen(button.code)) {
          const span = state.openSpans.get(button.code);
          void store.closeSpan(button.code, closeSpanEnd(span?.startMs ?? now, now));
        } else {
          void store.openSpan(button.code, { ...openSpanRange(now), code: button.code, template_id: template.id });
        }
        return;
      }
      void store.createTag({ ...instantRange(button, now, endMs || undefined), code: button.code, template_id: template.id });
    },
    [endMs, nowMs, state.openSpans, store, template],
  );

  const targetTagId = store.targetTagId();
  const targetTag = targetTagId ? (state.tags.get(targetTagId) ?? null) : null;

  const toggle = useCallback(
    (group: DescriptorGroup, value: string) => {
      const id = store.targetTagId();
      const tag = id ? store.get(id) : undefined;
      if (!tag) return;
      void store.updateTag(tag.id, { descriptors: toggleDescriptor(tag.descriptors, group, value) });
    },
    [store],
  );

  const splitSelected = useCallback(() => {
    const now = nowMs();
    const ids = [...state.selected];
    const candidate =
      (ids.length === 1 ? state.tags.get(ids[0]) : undefined) ??
      [...state.tags.values()].find((t) => t.start_ms < now && now < t.end_ms);
    if (candidate) void store.splitTag(candidate.id, now);
  }, [nowMs, state.selected, state.tags, store]);

  const mergeSelected = useCallback(() => {
    if (state.selected.size >= 2) void store.mergeTags([...state.selected]);
  }, [state.selected, store]);

  const deleteSelected = useCallback(() => {
    if (state.selected.size > 0) void store.deleteTags([...state.selected]);
  }, [state.selected, store]);

  // Keyboard ------------------------------------------------------------------------------
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return;
      const mod = event.metaKey || event.ctrlKey;
      if (mod && (event.key === 'z' || event.key === 'Z')) {
        event.preventDefault();
        if (event.shiftKey) void store.redo();
        else void store.undo();
        return;
      }
      if (event.ctrlKey && (event.key === 'y' || event.key === 'Y')) {
        event.preventDefault();
        void store.redo();
        return;
      }
      if (event.altKey && !mod) {
        if (event.code === 'KeyS') {
          event.preventDefault();
          splitSelected();
          return;
        }
        if (event.code === 'KeyM') {
          event.preventDefault();
          mergeSelected();
          return;
        }
      }
      if (event.key === 'Delete' || event.key === 'Backspace') {
        if (state.selected.size > 0) {
          event.preventDefault();
          deleteSelected();
        }
        return;
      }
      if (event.key === 'Escape') {
        store.clearSelection();
        return;
      }
      if (!template) return;
      const key = hotkeyFromEvent(event);
      if (!key) return;
      const button = findButton(template, key);
      if (button) {
        event.preventDefault();
        press(button);
        return;
      }
      const option = findOption(template, key);
      if (option) {
        event.preventDefault();
        toggle(option.group, option.option.value);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [deleteSelected, mergeSelected, press, splitSelected, state.selected.size, store, template, toggle]);

  // Close open spans when leaving the page.
  useEffect(() => {
    return () => {
      void store.closeAllSpans(nowMs());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store]);

  const rows: TimelineRow[] = useMemo(() => {
    const list: TimelineRow[] = (template?.buttons ?? []).map((b) => ({ code: b.code, label: b.label || b.code, colour: b.colour }));
    const known = new Set(list.map((r) => r.code));
    for (const tag of state.tags.values()) {
      if (!known.has(tag.code)) {
        known.add(tag.code);
        list.push({ code: tag.code, label: tag.code, colour: buttonForCode(template, tag.code)?.colour ?? fallbackColour(tag.code) });
      }
    }
    return list;
  }, [state.tags, template]);

  if (isPending) return <Loader />;
  if (!event) return <Alert color="red">Match not found.</Alert>;
  if (!canEdit(event.squad_id)) return <Alert color="red">Only analysts and admins can tag.</Alert>;

  return (
    <Stack gap="md">
      <Group justify="space-between" align="center" wrap="wrap">
        <Group gap="sm">
          <Button component={Link} to={`/matches/${event.id}`} variant="subtle" leftSection={<IconArrowLeft size={18} />} px={0}>
            Match
          </Button>
          <Title order={2} data-testid="tagging-title">
            Tagging: {event.display_title}
          </Title>
        </Group>
        <Group gap="xs">
          {templates && templates.length > 1 && (
            <Select aria-label="Template" data={templates.map((t) => ({ value: t.id, label: t.name }))} value={template?.id ?? null} onChange={setTemplateId} w={200} size="sm" />
          )}
          <Tooltip label="Undo (Cmd/Ctrl + Z)">
            <ActionIcon size="lg" variant="light" onClick={() => void store.undo()} disabled={!state.canUndo} aria-label="Undo" data-testid="undo">
              <IconArrowBackUp size={20} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Redo (Shift + Cmd/Ctrl + Z)">
            <ActionIcon size="lg" variant="light" onClick={() => void store.redo()} disabled={!state.canRedo} aria-label="Redo" data-testid="redo">
              <IconArrowForwardUp size={20} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Split at the playhead (Alt + S)">
            <ActionIcon size="lg" variant="light" onClick={splitSelected} aria-label="Split" data-testid="split">
              <IconCut size={20} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Merge the selected tags (Alt + M)">
            <ActionIcon size="lg" variant="light" onClick={mergeSelected} disabled={state.selected.size < 2} aria-label="Merge" data-testid="merge">
              <IconArrowsJoin size={20} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Delete the selected tags (Delete)">
            <ActionIcon size="lg" variant="light" color="red" onClick={deleteSelected} disabled={state.selected.size === 0} aria-label="Delete" data-testid="delete-tags">
              <IconTrash size={20} />
            </ActionIcon>
          </Tooltip>
          <Popover opened={helpOpen} onChange={setHelpOpen} position="bottom-end" withArrow shadow="md">
            <Popover.Target>
              <Tooltip label="Tagging shortcuts">
                <ActionIcon size="lg" variant="subtle" onClick={() => setHelpOpen((o) => !o)} aria-label="Tagging shortcuts">
                  <IconKeyboard size={20} />
                </ActionIcon>
              </Tooltip>
            </Popover.Target>
            <Popover.Dropdown>
              <Table withRowBorders={false} verticalSpacing={4}>
                <Table.Tbody>
                  {SHORTCUTS.map(([keys, what]) => (
                    <Table.Tr key={keys}>
                      <Table.Td><Kbd>{keys}</Kbd></Table.Td>
                      <Table.Td>{what}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Popover.Dropdown>
          </Popover>
        </Group>
      </Group>

      {state.notice && (
        <Alert color="orange" icon={<IconAlertCircle size={18} />} withCloseButton onClose={() => store.clearNotice()} data-testid="tag-notice">
          {state.notice}
        </Alert>
      )}

      {!video && (
        <Alert color="yellow" icon={<IconAlertCircle size={18} />}>
          This match has no playable video yet. Upload one from the match page first.
        </Alert>
      )}

      <div className="tagging-grid">
        <div>
          {video && <VideoPlayer ref={playerRef} video={video} onTime={onTime} compact />}
        </div>
        <Paper withBorder p="md" radius="md" style={{ maxHeight: 640, overflowY: 'auto' }}>
          {template ? (
            <CodeWindow
              template={template}
              players={players ?? []}
              openSpans={state.openSpans}
              targetTag={targetTag}
              targetIsSelection={state.selected.size === 1}
              onPress={press}
              onToggleDescriptor={toggle}
              onSetPlayers={(ids) => targetTag && void store.updateTag(targetTag.id, { player_ids: ids })}
              onSetNote={(note) => targetTag && void store.updateTag(targetTag.id, { note })}
            />
          ) : (
            <Text c="dimmed">No tag template yet. Create one under Templates.</Text>
          )}
        </Paper>
      </div>

      <div>
        <Group justify="space-between" mb={4}>
          <Text size="sm" c="dimmed">
            {state.loading ? 'Loading tags…' : `${state.tags.size} tags`}
            {state.selected.size > 0 ? ` · ${state.selected.size} selected` : ''}
            {state.pending > 0 ? ' · saving…' : ''}
          </Text>
          <Text size="sm" c="dimmed">Click to select and seek · drag to move · drag an edge to trim · Shift+click or drag an empty area to select several</Text>
        </Group>
        <Timeline
          key={video?.id ?? 'no-video'}
          tags={state.tags}
          order={state.order}
          rows={rows}
          selected={state.selected}
          openSpans={state.openSpans}
          playheadMs={playheadMs}
          endMs={Math.max(endMs, 60_000)}
          offsetMs={offsetMs}
          fps={fps}
          following={playing}
          onSeek={seekToMs}
          onSelect={(ids, additive) => (additive ? ids.forEach((id) => store.toggleSelect(id)) : store.select(ids))}
          onMove={(id, start, end) => void store.updateTag(id, { start_ms: start, end_ms: end })}
        />
      </div>
    </Stack>
  );
}
