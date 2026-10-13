import { Badge, Button, Group, Loader, Modal, Paper, Stack, Text, TextInput, Title } from '@mantine/core';
import { IconPlus, IconShare } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { useCreatePlaylist, usePlaylists } from '../api/hooksM2';
import { useAuth } from '../auth/AuthContext';

export function PlaylistsPage() {
  const { squadId = '' } = useParams();
  const { me } = useAuth();
  const navigate = useNavigate();
  const { data: playlists, isPending } = usePlaylists(squadId);
  const create = useCreatePlaylist(squadId);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <div>
          <Title order={1}>Playlists</Title>
          <Text c="dimmed">Your playlists and the ones shared with you.</Text>
        </div>
        <Button size="lg" leftSection={<IconPlus size={20} />} onClick={() => setOpen(true)} data-testid="new-playlist">
          New playlist
        </Button>
      </Group>
      {isPending && <Loader />}
      {playlists && playlists.length === 0 && (
        <Paper withBorder p="xl" radius="md">
          <Text c="dimmed" ta="center">No playlists yet. Find some clips and save them, or start an empty one.</Text>
        </Paper>
      )}
      <Stack gap="sm" data-testid="playlist-list">
        {playlists?.map((p) => (
          <Paper key={p.id} withBorder p="md" radius="md" component={Link} to={`/playlists/${p.id}`} className="event-card" data-testid="playlist-card">
            <Group justify="space-between" wrap="wrap">
              <div>
                <Text fw={700} size="lg">{p.name}</Text>
                <Text c="dimmed" size="sm">
                  {p.item_count} clip{p.item_count === 1 ? '' : 's'} · {p.owner_id === me.id ? 'yours' : `by ${p.owner_name ?? 'someone'}`}
                  {p.filter_definition ? ' · from a search' : ''}
                </Text>
              </div>
              <Group gap="xs">
                {p.shared_with.length > 0 && (
                  <Badge variant="light" leftSection={<IconShare size={12} />}>
                    shared with {p.shared_with.length}
                  </Badge>
                )}
              </Group>
            </Group>
          </Paper>
        ))}
      </Stack>
      <Modal opened={open} onClose={() => setOpen(false)} title="New playlist">
        <Stack>
          <TextInput label="Name" value={name} onChange={(e) => setName(e.currentTarget.value)} data-autofocus data-testid="playlist-name" onKeyDown={(e) => e.key === 'Enter' && name.trim() && create.mutate({ name: name.trim() }, { onSuccess: (p) => navigate(`/playlists/${p.id}`) })} />
          <Button disabled={!name.trim()} loading={create.isPending} onClick={() => create.mutate({ name: name.trim() }, { onSuccess: (p) => navigate(`/playlists/${p.id}`) })} data-testid="playlist-create">
            Create
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
