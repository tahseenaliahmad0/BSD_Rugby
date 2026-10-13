import {
  Badge,
  Button,
  Group,
  Loader,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconPlus, IconSearch, IconVideo } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { useEvents, useSeasons, useSquads } from '../api/hooks';
import type { Event } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { formatDate } from '../components/format';
import { rememberSquad } from '../components/squadMemory';

function videoBadge(event: Event) {
  if (event.video_count === 0) return <Badge color="gray" variant="light">No video yet</Badge>;
  return (
    <Badge color="green" variant="light" leftSection={<IconVideo size={14} />}>
      {event.video_count === 1 ? '1 video' : `${event.video_count} videos`}
    </Badge>
  );
}

export function LibraryPage() {
  const { squadId = '' } = useParams();
  const navigate = useNavigate();
  const { canEdit } = useAuth();
  const { data: squads } = useSquads();
  const squad = squads?.find((s) => s.id === squadId);
  const [seasonId, setSeasonId] = useState<string>('all');
  const [type, setType] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [debouncedSearch] = useDebouncedValue(search, 250);

  useEffect(() => {
    if (squadId) rememberSquad(squadId);
  }, [squadId]);

  const { data: seasons } = useSeasons(squadId);
  const { data: events, isPending, error } = useEvents(squadId, {
    season_id: seasonId === 'all' ? undefined : seasonId,
    type: type === 'all' ? undefined : type,
    q: debouncedSearch || undefined,
  });

  const seasonOptions = [
    { value: 'all', label: 'All seasons' },
    ...(seasons ?? []).map((s) => ({ value: s.id, label: s.name })),
  ];

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <div>
          <Title order={1}>{squad?.name ?? 'Library'}</Title>
          <Text c="dimmed">Matches and training sessions</Text>
        </div>
        {canEdit(squadId) && (
          <Button
            size="lg"
            leftSection={<IconPlus size={20} />}
            onClick={() => navigate(`/squads/${squadId}/matches/new`)}
            data-testid="new-match"
          >
            New match
          </Button>
        )}
      </Group>

      <Group wrap="wrap" gap="md">
        <Select
          aria-label="Season"
          data={seasonOptions}
          value={seasonId}
          onChange={(v) => setSeasonId(v ?? 'all')}
          allowDeselect={false}
          w={200}
        />
        <SegmentedControl
          aria-label="Type"
          value={type}
          onChange={setType}
          data={[
            { value: 'all', label: 'All' },
            { value: 'match', label: 'Matches' },
            { value: 'training', label: 'Training' },
          ]}
        />
        <TextInput
          aria-label="Search"
          placeholder="Search opponent, competition or venue"
          leftSection={<IconSearch size={18} />}
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          w={320}
          maw="100%"
        />
      </Group>

      {isPending && <Loader />}
      {error && <Text c="red">Could not load the library: {error.message}</Text>}
      {events && events.length === 0 && (
        <Paper withBorder p="xl" radius="md">
          <Text c="dimmed" ta="center">
            {search || seasonId !== 'all' || type !== 'all'
              ? 'Nothing matches those filters.'
              : canEdit(squadId)
                ? 'No matches yet. Create one with the New match button, then upload the video.'
                : 'No matches yet. Your analyst will add them here.'}
          </Text>
        </Paper>
      )}
      <Stack gap="sm" data-testid="event-list">
        {events?.map((event) => (
          <Paper
            key={event.id}
            withBorder
            p="md"
            radius="md"
            component={Link}
            to={`/matches/${event.id}`}
            className="event-card"
            data-testid="event-card"
          >
            <Group justify="space-between" wrap="wrap">
              <div>
                <Text fw={700} size="lg">
                  {event.display_title}
                </Text>
                <Text c="dimmed">
                  {formatDate(event.date)}
                  {event.competition ? ` · ${event.competition}` : ''}
                  {event.venue ? ` · ${event.venue}` : ''}
                </Text>
              </div>
              <Group gap="xs">
                <Badge variant="outline" color={event.type === 'match' ? 'green' : 'blue'}>
                  {event.type === 'match' ? 'Match' : 'Training'}
                </Badge>
                {videoBadge(event)}
              </Group>
            </Group>
          </Paper>
        ))}
      </Stack>
    </Stack>
  );
}
