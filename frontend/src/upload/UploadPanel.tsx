import { Alert, Button, Group, Paper, Progress, Stack, Text, Title } from '@mantine/core';
import { IconAlertCircle, IconCheck, IconUpload } from '@tabler/icons-react';
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import * as tus from 'tus-js-client';
import { api, CSRF_HEADER, csrfToken } from '../api/client';
import type { UploadInfo } from '../api/types';
import { formatBytes, formatEta } from '../components/format';

type Phase = 'idle' | 'uploading' | 'paused' | 'finishing' | 'done' | 'error';

interface Props {
  eventId: string;
  hasVideo: boolean;
  onUploaded: (videoId: string) => void;
}

const CHUNK_BYTES = 32 * 1024 * 1024;

export function UploadPanel({ eventId, hasVideo, onUploaded }: Props) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [file, setFile] = useState<File | null>(null);
  const [uploaded, setUploaded] = useState(0);
  const [total, setTotal] = useState(0);
  const [speed, setSpeed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const uploadRef = useRef<tus.Upload | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const speedSample = useRef<{ at: number; bytes: number } | null>(null);

  useEffect(
    () => () => {
      void uploadRef.current?.abort();
    },
    [],
  );

  const start = (chosen: File) => {
    setFile(chosen);
    setError(null);
    setUploaded(0);
    setTotal(chosen.size);
    setSpeed(0);
    speedSample.current = null;
    setPhase('uploading');

    const upload = new tus.Upload(chosen, {
      endpoint: '/api/uploads',
      chunkSize: CHUNK_BYTES,
      retryDelays: [0, 1000, 3000, 5000, 10000, 20000],
      removeFingerprintOnSuccess: true,
      metadata: {
        filename: chosen.name,
        filetype: chosen.type,
        eventId,
        cameraLabel: 'Main',
      },
      headers: { [CSRF_HEADER]: csrfToken() },
      onError: (err) => {
        setError(err.message);
        setPhase('error');
      },
      onProgress: (bytesUploaded, bytesTotal) => {
        setUploaded(bytesUploaded);
        setTotal(bytesTotal);
        const now = performance.now();
        const sample = speedSample.current;
        if (sample && now - sample.at > 500) {
          const instant = ((bytesUploaded - sample.bytes) * 1000) / (now - sample.at);
          setSpeed((prev) => (prev ? prev * 0.7 + instant * 0.3 : instant));
          speedSample.current = { at: now, bytes: bytesUploaded };
        } else if (!sample) {
          speedSample.current = { at: now, bytes: bytesUploaded };
        }
      },
      onSuccess: async () => {
        setPhase('finishing');
        try {
          const url = upload.url ?? '';
          const info = await api<UploadInfo>(url);
          if (!info.video_id) throw new Error('The server did not create a video.');
          setPhase('done');
          onUploaded(info.video_id);
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
          setPhase('error');
        }
      },
    });
    uploadRef.current = upload;

    upload
      .findPreviousUploads()
      .then((previous) => {
        const same = previous.find((p) => p.metadata?.eventId === eventId);
        if (same) upload.resumeFromPreviousUpload(same);
        upload.start();
      })
      .catch(() => upload.start());
  };

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0];
    if (chosen) start(chosen);
    event.target.value = '';
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const chosen = event.dataTransfer.files?.[0];
    if (chosen) start(chosen);
  };

  const pause = () => {
    uploadRef.current?.abort();
    setPhase('paused');
  };
  const resume = () => {
    uploadRef.current?.start();
    setPhase('uploading');
  };
  const cancel = () => {
    void uploadRef.current?.abort(true);
    uploadRef.current = null;
    setPhase('idle');
    setFile(null);
  };

  const percent = total > 0 ? (uploaded / total) * 100 : 0;
  const remaining = speed > 0 ? (total - uploaded) / speed : Number.NaN;

  return (
    <Paper withBorder p="lg" radius="md" data-testid="upload-panel">
      <Stack gap="md">
        <Title order={3}>{hasVideo ? 'Add another video' : 'Upload the match video'}</Title>

        {(phase === 'idle' || phase === 'done' || phase === 'error') && (
          <div
            className={`drop-zone${dragging ? ' active' : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click();
            }}
            data-testid="upload-dropzone"
          >
            <Stack gap="xs" align="center">
              <IconUpload size={40} />
              <Text fw={600} size="lg">
                Choose a video file
              </Text>
              <Text c="dimmed">or drag it here. Large files are fine; an interrupted upload resumes.</Text>
            </Stack>
            <input
              ref={inputRef}
              type="file"
              accept="video/*,.mp4,.mov,.mts,.m2ts,.mkv,.avi"
              style={{ display: 'none' }}
              onChange={onPick}
              data-testid="upload-input"
            />
          </div>
        )}

        {file && phase !== 'idle' && (
          <Stack gap="xs" data-testid="upload-progress">
            <Group justify="space-between">
              <Text fw={600}>{file.name}</Text>
              <Text c="dimmed">
                {formatBytes(uploaded)} of {formatBytes(total)}
              </Text>
            </Group>
            <Progress
              value={phase === 'done' || phase === 'finishing' ? 100 : percent}
              size="xl"
              animated={phase === 'uploading'}
              color={phase === 'error' ? 'red' : phase === 'done' ? 'green' : undefined}
            />
            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                {phase === 'uploading' &&
                  `${Math.round(percent)}% · ${speed > 0 ? `${formatBytes(speed)}/s` : 'starting'} ${formatEta(remaining)}`}
                {phase === 'paused' && 'Paused'}
                {phase === 'finishing' && 'Upload complete. Starting processing...'}
                {phase === 'done' && (
                  <Group gap={4} component="span">
                    <IconCheck size={16} /> Uploaded. Processing continues below.
                  </Group>
                )}
              </Text>
              <Group gap="xs">
                {phase === 'uploading' && (
                  <Button variant="light" onClick={pause}>
                    Pause
                  </Button>
                )}
                {phase === 'paused' && (
                  <Button onClick={resume}>Resume</Button>
                )}
                {(phase === 'uploading' || phase === 'paused' || phase === 'error') && (
                  <Button variant="subtle" color="red" onClick={cancel}>
                    Cancel
                  </Button>
                )}
              </Group>
            </Group>
          </Stack>
        )}

        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            Upload problem: {error}. Choose the same file again to resume where it stopped.
          </Alert>
        )}
      </Stack>
    </Paper>
  );
}
