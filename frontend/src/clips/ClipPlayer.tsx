import { Alert, Group, Stack, Text } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { forwardRef } from 'react';
import type { Clip } from '../api/types';
import { formatDate } from '../components/format';
import { VideoPlayer, type PlayerHandle } from '../player/VideoPlayer';
import { clipTitle } from './clipLabel';

interface Props {
  clip: Clip;
  autoPlay?: boolean;
  onEnded?: () => void;
  keyboard?: boolean;
  compact?: boolean;
  note?: string | null;
}

/** Plays one clip (a tag or a range) from its video, bounded to the clip's start and end. */
export const ClipPlayer = forwardRef<PlayerHandle, Props>(function ClipPlayer(
  { clip, autoPlay = false, onEnded, keyboard = true, compact = false, note },
  ref,
) {
  return (
    <Stack gap="xs">
      <Group justify="space-between" align="baseline" wrap="wrap">
        <Text fw={700} size="lg" data-testid="clip-title">
          {clipTitle(clip)}
        </Text>
        <Text c="dimmed" size="sm">
          {clip.event.display_title} · {formatDate(clip.event.date)}
        </Text>
      </Group>
      {note && (
        <Text size="sm" c="dimmed" fs="italic">
          {note}
        </Text>
      )}
      {clip.video && clip.start_s !== null && clip.end_s !== null ? (
        <VideoPlayer
          ref={ref}
          video={clip.video}
          clipStartS={clip.start_s}
          clipEndS={clip.end_s}
          autoPlay={autoPlay}
          onClipEnd={onEnded}
          keyboard={keyboard}
          compact={compact}
        />
      ) : (
        <Alert color="yellow" icon={<IconAlertCircle size={18} />}>
          The video for this match has not been uploaded yet.
        </Alert>
      )}
    </Stack>
  );
});
