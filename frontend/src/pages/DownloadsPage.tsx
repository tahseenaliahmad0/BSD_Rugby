import { ActionIcon, Badge, Button, Group, Loader, Paper, Progress, Stack, Text, Title, Tooltip } from '@mantine/core';
import { IconDownload, IconTrash } from '@tabler/icons-react';
import { useParams } from 'react-router';
import { useDeleteExport, useExports } from '../api/hooksM2';
import { useAuth } from '../auth/AuthContext';
import { formatBytes } from '../components/format';

const COLOUR: Record<string, string> = { queued: 'yellow', running: 'blue', succeeded: 'green', failed: 'red', cancelled: 'gray' };
const LABEL: Record<string, string> = { queued: 'Waiting', running: 'Making the video', succeeded: 'Ready', failed: 'Failed', cancelled: 'Cancelled' };

export function DownloadsPage() {
  const { squadId = '' } = useParams();
  const { me, roleIn } = useAuth();
  const { data: exports, isPending } = useExports(squadId);
  const remove = useDeleteExport(squadId);
  const isAdmin = roleIn(squadId) === 'admin';

  return (
    <Stack gap="lg">
      <div>
        <Title order={1}>Downloads</Title>
        <Text c="dimmed">Exported clips and playlists. Files stay here until someone deletes them.</Text>
      </div>
      {isPending && <Loader />}
      {exports && exports.length === 0 && (
        <Paper withBorder p="xl" radius="md">
          <Text c="dimmed" ta="center">Nothing exported yet. Open a playlist and choose Export MP4.</Text>
        </Paper>
      )}
      <Stack gap="sm" data-testid="export-list">
        {exports?.map((e) => (
          <Paper key={e.id} withBorder p="md" radius="md" data-testid="export-row">
            <Group justify="space-between" wrap="wrap" align="flex-start">
              <div style={{ minWidth: 0, flex: 1 }}>
                <Group gap="xs">
                  <Text fw={700}>{e.name}</Text>
                  <Badge color={COLOUR[e.status] ?? 'gray'} variant="light" data-testid="export-status">{LABEL[e.status] ?? e.status}</Badge>
                </Group>
                <Text size="sm" c="dimmed">
                  {e.clip_count} clip{e.clip_count === 1 ? '' : 's'} · {e.owner_name ?? 'someone'} · {new Date(e.created_at).toLocaleString()}
                  {e.size_bytes ? ` · ${formatBytes(e.size_bytes)}` : ''}
                </Text>
                {(e.status === 'queued' || e.status === 'running') && <Progress value={Math.round(e.progress * 100)} size="md" mt="xs" animated striped />}
                {e.status === 'failed' && <Text size="sm" c="red" mt={4}>{e.error}</Text>}
              </div>
              <Group gap="xs">
                {e.status === 'succeeded' && e.file_url && (
                  <Button component="a" href={e.file_url} download leftSection={<IconDownload size={18} />} data-testid="export-download">
                    Download
                  </Button>
                )}
                {(e.owner_id === me.id || isAdmin) && (
                  <Tooltip label="Delete this file">
                    <ActionIcon size="lg" variant="subtle" color="red" aria-label="Delete" onClick={() => remove.mutate(e.id)} data-testid="export-delete">
                      <IconTrash size={18} />
                    </ActionIcon>
                  </Tooltip>
                )}
              </Group>
            </Group>
          </Paper>
        ))}
      </Stack>
    </Stack>
  );
}
