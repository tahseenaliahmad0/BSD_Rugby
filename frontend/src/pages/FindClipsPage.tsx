/**
 * Find clips: plain-language chips for codes and descriptors, roster and match filters, and a
 * result list with thumbnails. Every action works with the mouse; no timeline or code window.
 */
import {
  Badge,
  Button,
  Checkbox,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconDeviceFloppy, IconTrash, IconX } from '@tabler/icons-react';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { useEvents, useOpponents, useSeasons } from '../api/hooks';
import {
  useCreateSavedFilter,
  useDeleteSavedFilter,
  usePlayers,
  useSavedFilters,
  useSearchClips,
  useTemplates,
} from '../api/hooksM2';
import type { Clip, FilterDefinition } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { AddToPlaylist } from '../clips/AddToPlaylist';
import { clipDurationS, clipTitle } from '../clips/clipLabel';
import { ClipPlayer } from '../clips/ClipPlayer';
import { formatDate } from '../components/format';

function toggleIn(list: string[] | undefined, value: string): string[] {
  const current = list ?? [];
  return current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
}

function isEmpty(f: FilterDefinition): boolean {
  return !(
    f.codes?.length ||
    Object.values(f.descriptors ?? {}).some((v) => v.length) ||
    f.player_ids?.length ||
    f.event_ids?.length ||
    f.season_ids?.length ||
    f.opponent_ids?.length ||
    f.event_types?.length ||
    f.text
  );
}

export function FindClipsPage() {
  const { squadId = '' } = useParams();
  const { me } = useAuth();
  const { data: templates } = useTemplates(squadId);
  const { data: players } = usePlayers(squadId);
  const { data: seasons } = useSeasons(squadId);
  const { data: opponents } = useOpponents(squadId);
  const { data: events } = useEvents(squadId, {});
  const { data: savedFilters } = useSavedFilters(squadId);
  const createSaved = useCreateSavedFilter(squadId);
  const deleteSaved = useDeleteSavedFilter(squadId);

  const [filter, setFilter] = useState<FilterDefinition>({});
  const [playing, setPlaying] = useState<Clip | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveShared, setSaveShared] = useState(false);

  const template = templates?.find((t) => t.name.includes('15s')) ?? templates?.[0];
  const { data: result, isFetching } = useSearchClips(squadId, filter, 200, 0);

  const optionGroups = useMemo(() => (template?.descriptor_groups ?? []).filter((g) => g.kind === 'options'), [template]);
  const playerOptions = useMemo(
    () =>
      [...(players ?? [])]
        .sort((a, b) => (a.shirt_number ?? 99) - (b.shirt_number ?? 99))
        .map((p) => ({ value: p.id, label: p.shirt_number != null ? `${p.shirt_number}  ${p.name}` : p.name })),
    [players],
  );

  const setDescriptor = (key: string, value: string) =>
    setFilter((f) => {
      const descriptors = { ...(f.descriptors ?? {}) };
      const next = toggleIn(descriptors[key], value);
      if (next.length) descriptors[key] = next;
      else delete descriptors[key];
      return { ...f, descriptors };
    });

  const clips = result?.clips ?? [];

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <div>
          <Title order={1}>Find clips</Title>
          <Text c="dimmed">Pick what you want to see. Clips from every match in the squad are included.</Text>
        </div>
        <Group>
          {savedFilters && savedFilters.length > 0 && (
            <Select
              placeholder="Saved searches"
              aria-label="Saved searches"
              data={savedFilters.map((s) => ({ value: s.id, label: s.is_shared && s.owner_id !== me.id ? `${s.name} (${s.owner_name})` : s.name }))}
              onChange={(id) => {
                const saved = savedFilters.find((s) => s.id === id);
                if (saved) setFilter(saved.definition);
              }}
              clearable
              w={240}
              data-testid="saved-filters"
            />
          )}
          <Button variant="light" leftSection={<IconDeviceFloppy size={18} />} disabled={isEmpty(filter)} onClick={() => setSaveOpen(true)} data-testid="save-filter">
            Save this search
          </Button>
          {!isEmpty(filter) && (
            <Button variant="subtle" leftSection={<IconX size={18} />} onClick={() => setFilter({})}>
              Clear
            </Button>
          )}
        </Group>
      </Group>

      <Paper withBorder p="md" radius="md">
        <Stack gap="md">
          <div>
            <Text fw={600} mb={6}>What happened</Text>
            <Group gap={8}>
              {(template?.buttons ?? []).map((b) => {
                const on = filter.codes?.includes(b.code) ?? false;
                return (
                  <button key={b.code} type="button" className={`chip-btn${on ? ' on' : ''}`} style={on ? { backgroundColor: b.colour, borderColor: b.colour } : undefined} onClick={() => setFilter((f) => ({ ...f, codes: toggleIn(f.codes, b.code) }))} aria-pressed={on} data-testid={`chip-code-${b.code}`}>
                    {b.label || b.code}
                  </button>
                );
              })}
              {!template && <Text c="dimmed">No tag template yet.</Text>}
            </Group>
          </div>
          {optionGroups.map((group) => (
            <div key={group.key}>
              <Text fw={600} mb={6}>{group.label}</Text>
              <Group gap={8}>
                {group.options.map((o) => {
                  const on = filter.descriptors?.[group.key]?.includes(o.value) ?? false;
                  return (
                    <button key={o.value} type="button" className={`chip-btn${on ? ' on' : ''}`} onClick={() => setDescriptor(group.key, o.value)} aria-pressed={on} data-testid={`chip-${group.key}-${o.value}`}>
                      {o.label || o.value}
                    </button>
                  );
                })}
              </Group>
            </div>
          ))}
          <Group align="flex-end" wrap="wrap">
            <MultiSelect label="Players" placeholder="Any player" data={playerOptions} value={filter.player_ids ?? []} onChange={(v) => setFilter((f) => ({ ...f, player_ids: v }))} searchable w={260} />
            <Select label="Match" placeholder="Any match" data={(events ?? []).map((e) => ({ value: e.id, label: `${e.display_title} · ${formatDate(e.date)}` }))} value={filter.event_ids?.[0] ?? null} onChange={(v) => setFilter((f) => ({ ...f, event_ids: v ? [v] : [] }))} clearable searchable w={280} />
            <Select label="Season" placeholder="Any season" data={(seasons ?? []).map((s) => ({ value: s.id, label: s.name }))} value={filter.season_ids?.[0] ?? null} onChange={(v) => setFilter((f) => ({ ...f, season_ids: v ? [v] : [] }))} clearable w={180} />
            <Select label="Opponent" placeholder="Any opponent" data={(opponents ?? []).map((o) => ({ value: o.id, label: o.name }))} value={filter.opponent_ids?.[0] ?? null} onChange={(v) => setFilter((f) => ({ ...f, opponent_ids: v ? [v] : [] }))} clearable searchable w={200} />
            <div>
              <Text size="sm" fw={500} mb={4}>Type</Text>
              <SegmentedControl value={filter.event_types?.[0] ?? 'all'} onChange={(v) => setFilter((f) => ({ ...f, event_types: v === 'all' ? [] : [v as 'match' | 'training'] }))} data={[{ value: 'all', label: 'All' }, { value: 'match', label: 'Matches' }, { value: 'training', label: 'Training' }]} />
            </div>
          </Group>
        </Stack>
      </Paper>

      {playing && (
        <Paper withBorder p="md" radius="md" data-testid="clip-player-panel">
          <ClipPlayer clip={playing} autoPlay />
          <Group mt="sm">
            <Button variant="subtle" onClick={() => setPlaying(null)}>Close</Button>
            {playing.tag && <AddToPlaylist squadId={squadId} tagIds={[playing.tag.id]} />}
          </Group>
        </Paper>
      )}

      <Group justify="space-between" align="center">
        <Text fw={600} data-testid="clip-count">
          {result ? `${result.total} clip${result.total === 1 ? '' : 's'}` : ''} {isFetching && <Loader size="xs" ml="xs" />}
        </Text>
        {result && result.total > 0 && <AddToPlaylist squadId={squadId} filter={filter} label="Save all as a playlist" variant="filled" size="md" />}
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} data-testid="clip-results">
        {clips.map((clip) => (
          <Paper key={clip.tag?.id ?? `${clip.event.id}-${clip.start_ms}`} withBorder p="sm" radius="md" className="clip-card" onClick={() => setPlaying(clip)} data-testid="clip-card">
            {clip.thumbnail_url ? (
              <img className="clip-thumb" src={clip.thumbnail_url} alt="" loading="lazy" />
            ) : (
              <div className="clip-thumb" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#888' }}>No video yet</div>
            )}
            <Text fw={600} mt="xs" lineClamp={2}>{clipTitle(clip)}</Text>
            <Group justify="space-between" mt={4}>
              <Text size="sm" c="dimmed" lineClamp={1}>{clip.event.display_title} · {formatDate(clip.event.date)}</Text>
              <Badge variant="light" color="gray">{clipDurationS(clip).toFixed(0)} s</Badge>
            </Group>
          </Paper>
        ))}
      </SimpleGrid>
      {result && result.total === 0 && (
        <Text c="dimmed" ta="center" py="xl">Nothing matches yet. Try fewer chips.</Text>
      )}

      <Modal opened={saveOpen} onClose={() => setSaveOpen(false)} title="Save this search">
        <Stack>
          <TextInput label="Name" placeholder="For example: Lost lineouts in their 22" value={saveName} onChange={(e) => setSaveName(e.currentTarget.value)} data-autofocus data-testid="save-filter-name" />
          <Checkbox label="Share with everyone in the squad" checked={saveShared} onChange={(e) => setSaveShared(e.currentTarget.checked)} />
          <Button
            loading={createSaved.isPending}
            disabled={!saveName.trim()}
            onClick={() =>
              createSaved.mutate(
                { name: saveName.trim(), definition: filter, is_shared: saveShared },
                {
                  onSuccess: () => {
                    notifications.show({ color: 'green', message: 'Search saved.' });
                    setSaveOpen(false);
                    setSaveName('');
                  },
                },
              )
            }
            data-testid="save-filter-confirm"
          >
            Save
          </Button>
          {savedFilters && savedFilters.filter((s) => s.owner_id === me.id).length > 0 && (
            <Stack gap={4}>
              <Text size="sm" fw={600}>Your saved searches</Text>
              {savedFilters.filter((s) => s.owner_id === me.id).map((s) => (
                <Group key={s.id} justify="space-between">
                  <Text size="sm">{s.name}{s.is_shared ? ' (shared)' : ''}</Text>
                  <Button size="compact-xs" variant="subtle" color="red" leftSection={<IconTrash size={14} />} onClick={() => deleteSaved.mutate(s.id)}>
                    Delete
                  </Button>
                </Group>
              ))}
            </Stack>
          )}
        </Stack>
      </Modal>
    </Stack>
  );
}
