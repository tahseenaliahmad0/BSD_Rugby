import {
  Alert,
  Autocomplete,
  Button,
  Group,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconAlertCircle, IconArrowLeft } from '@tabler/icons-react';
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router';
import { ApiError } from '../api/client';
import { useCreateEvent, useOpponents, useSeasons } from '../api/hooks';
import type { EventType } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { todayIso } from '../components/format';

export function NewMatchPage() {
  const { squadId = '' } = useParams();
  const navigate = useNavigate();
  const { canEdit } = useAuth();
  const { data: seasons } = useSeasons(squadId);
  const { data: opponents } = useOpponents(squadId);
  const create = useCreateEvent(squadId);

  const [type, setType] = useState<EventType>('match');
  const [date, setDate] = useState(todayIso());
  const [opponent, setOpponent] = useState('');
  const [title, setTitle] = useState('');
  const [competition, setCompetition] = useState('');
  const [venue, setVenue] = useState('');
  const [homeAway, setHomeAway] = useState('home');
  const [seasonId, setSeasonId] = useState<string | null>(seasons?.[0]?.id ?? null);

  if (!canEdit(squadId)) return <Navigate to={`/squads/${squadId}`} replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      {
        type,
        date,
        title: title.trim() || null,
        opponent_name: type === 'match' ? opponent.trim() || null : null,
        competition: competition.trim() || null,
        venue: venue.trim() || null,
        is_home: type === 'match' ? (homeAway === 'neutral' ? null : homeAway === 'home') : null,
        season_id: seasonId,
      },
      { onSuccess: (created) => navigate(`/matches/${created.id}`, { replace: true }) },
    );
  };

  const message =
    create.error instanceof ApiError ? create.error.detail : create.error ? create.error.message : null;

  return (
    <Stack gap="lg" maw={640}>
      <Button
        component={Link}
        to={`/squads/${squadId}`}
        variant="subtle"
        leftSection={<IconArrowLeft size={18} />}
        w="fit-content"
      >
        Back to library
      </Button>
      <Title order={1}>New {type === 'match' ? 'match' : 'training session'}</Title>
      <Paper withBorder p="xl" radius="md">
        <form onSubmit={submit}>
          <Stack gap="md">
            <SegmentedControl
              value={type}
              onChange={(v) => setType(v as EventType)}
              data={[
                { value: 'match', label: 'Match' },
                { value: 'training', label: 'Training' },
              ]}
              size="lg"
            />
            <TextInput
              label="Date"
              type="date"
              required
              value={date}
              onChange={(e) => setDate(e.currentTarget.value)}
              data-testid="match-date"
            />
            {type === 'match' ? (
              <Autocomplete
                label="Opponent"
                placeholder="Who did we play?"
                data={(opponents ?? []).map((o) => o.name)}
                value={opponent}
                onChange={setOpponent}
                required
                data-testid="match-opponent"
              />
            ) : (
              <TextInput
                label="Session name"
                placeholder="For example: Lineout session"
                value={title}
                onChange={(e) => setTitle(e.currentTarget.value)}
                data-testid="match-title"
              />
            )}
            {type === 'match' && (
              <>
                <SegmentedControl
                  value={homeAway}
                  onChange={setHomeAway}
                  data={[
                    { value: 'home', label: 'Home' },
                    { value: 'away', label: 'Away' },
                    { value: 'neutral', label: 'Neutral' },
                  ]}
                />
                <TextInput
                  label="Competition"
                  placeholder="League, cup, friendly..."
                  value={competition}
                  onChange={(e) => setCompetition(e.currentTarget.value)}
                />
              </>
            )}
            <TextInput
              label="Venue"
              placeholder="Optional"
              value={venue}
              onChange={(e) => setVenue(e.currentTarget.value)}
            />
            <Select
              label="Season"
              data={(seasons ?? []).map((s) => ({ value: s.id, label: s.name }))}
              value={seasonId}
              onChange={setSeasonId}
              placeholder={seasons && seasons.length ? 'Choose a season' : 'No seasons yet'}
              clearable
            />
            {message && (
              <Alert color="red" icon={<IconAlertCircle size={18} />}>
                {message}
              </Alert>
            )}
            <Group justify="flex-end">
              <Button type="submit" size="lg" loading={create.isPending} data-testid="match-create">
                Create and upload video
              </Button>
            </Group>
            <Text c="dimmed" size="sm">
              You can upload the video on the next screen.
            </Text>
          </Stack>
        </form>
      </Paper>
    </Stack>
  );
}
