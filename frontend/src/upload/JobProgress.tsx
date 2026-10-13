import { Group, Progress, Text } from '@mantine/core';
import { useVideoJobs } from '../api/hooks';

/** Live progress of the latest job for a video (transcode), polled while it runs. */
export function JobProgress({ videoId }: { videoId: string }) {
  const { data: jobs } = useVideoJobs(videoId, true);
  const job = jobs?.[jobs.length - 1];
  if (!job) return null;
  const percent = Math.round(job.progress * 100);
  const animated = job.status === 'queued' || job.status === 'running';
  return (
    <div data-testid="job-progress">
      <Group justify="space-between" mt="sm" mb={4}>
        <Text size="sm">{job.message ?? job.status}</Text>
        <Text size="sm" c="dimmed">
          {percent}%
        </Text>
      </Group>
      <Progress value={percent} size="lg" animated={animated} striped={animated} />
    </div>
  );
}
