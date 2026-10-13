import {
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconAlertCircle, IconArrowLeft, IconPlayerPlay, IconTags } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useEvent } from '../api/hooks';
import type { Video } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { formatBytes, formatDate } from '../components/format';
import { formatClock } from '../player/frameMath';
import { VideoPlayer } from '../player/VideoPlayer';
import { JobProgress } from '../upload/JobProgress';
import { UploadPanel } from '../upload/UploadPanel';

const STATUS_LABEL: Record<Video['status'], { label: string; color: string }> = {
  uploading: { label: 'Uploading', color: 'blue' },
  queued: { label: 'Waiting to process', color: 'yellow' },
  processing: { label: 'Processing', color: 'yellow' },
  ready: { label: 'Ready', color: 'green' },
  failed: { label: 'Failed', color: 'red' },
};

export function MatchPage() {
  const { eventId = '' } = useParams();
  const { data: event, isPending, error, refetch } = useEvent(eventId);
  const { canEdit } = useAuth();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const videos = event?.videos ?? [];
  const readyVideos = videos.filter((v) => v.status === 'ready');
  const selected = readyVideos.find((v) => v.id === selectedId) ?? readyVideos[0] ?? null;

  if (isPending) return <Loader />;
  if (error || !event) {
    return (
      <Alert color="red" icon={<IconAlertCircle size={18} />}>
        Could not load this match. {error?.message}
      </Alert>
    );
  }

  const editable = canEdit(event.squad_id);

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <div>
          <Button
            component={Link}
            to={`/squads/${event.squad_id}`}
            variant="subtle"
            leftSection={<IconArrowLeft size={18} />}
            px={0}
          >
            Back to library
          </Button>
          <Title order={1} data-testid="match-title">
            {event.display_title}
          </Title>
          <Text c="dimmed">
            {formatDate(event.date)}
            {event.competition ? ` · ${event.competition}` : ''}
            {event.venue ? ` · ${event.venue}` : ''}
            {event.is_home === true ? ' · Home' : event.is_home === false ? ' · Away' : ''}
          </Text>
        </div>
        {editable && readyVideos.length > 0 && (
          <Button component={Link} to={`/matches/${event.id}/tag`} size="lg" leftSection={<IconTags size={20} />} data-testid="tag-match">
            Tag this match
          </Button>
        )}
      </Group>

      {selected && (
        <VideoPlayer key={selected.id} video={selected} />
      )}

      {videos.length === 0 && !editable && (
        <Paper withBorder p="xl" radius="md">
          <Text c="dimmed" ta="center">
            No video yet. Your analyst will upload it after the match.
          </Text>
        </Paper>
      )}

      {videos.length > 0 && (
        <Stack gap="sm" data-testid="video-list">
          {videos.map((video) => {
            const status = STATUS_LABEL[video.status];
            const busy = video.status === 'queued' || video.status === 'processing';
            return (
              <Paper key={video.id} withBorder p="md" radius="md" data-testid="video-row">
                <Group justify="space-between" wrap="wrap">
                  <div>
                    <Group gap="xs">
                      <Text fw={600}>{video.camera_label}</Text>
                      <Badge color={status.color} variant="light" data-testid="video-status">
                        {status.label}
                      </Badge>
                    </Group>
                    <Text c="dimmed" size="sm">
                      {video.original_filename} · {formatBytes(video.original_size_bytes)}
                      {video.duration_s && video.fps
                        ? ` · ${formatClock(video.duration_s)} · ${video.width}x${video.height} · ${video.fps.toFixed(2)} fps`
                        : ''}
                    </Text>
                  </div>
                  {video.status === 'ready' && readyVideos.length > 1 && (
                    <Button
                      variant={selected?.id === video.id ? 'filled' : 'light'}
                      leftSection={<IconPlayerPlay size={18} />}
                      onClick={() => setSelectedId(video.id)}
                    >
                      {selected?.id === video.id ? 'Watching' : 'Watch'}
                    </Button>
                  )}
                </Group>
                {busy && <JobProgress videoId={video.id} />}
                {video.status === 'failed' && (
                  <Alert color="red" mt="sm" icon={<IconAlertCircle size={18} />}>
                    Processing failed. {video.error}
                  </Alert>
                )}
              </Paper>
            );
          })}
        </Stack>
      )}

      {editable && (
        <UploadPanel
          eventId={event.id}
          hasVideo={videos.length > 0}
          onUploaded={() => {
            void refetch();
          }}
        />
      )}
    </Stack>
  );
}
