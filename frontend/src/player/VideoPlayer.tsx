import {
  ActionIcon,
  Group,
  Kbd,
  Loader,
  Popover,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Tooltip,
} from '@mantine/core';
import {
  IconArrowBarToLeft,
  IconArrowBarToRight,
  IconKeyboard,
  IconMaximize,
  IconMinimize,
  IconPlayerPause,
  IconPlayerPlay,
  IconPlayerSkipBack,
  IconPlayerSkipForward,
  IconRewindBackward5,
  IconRewindForward5,
  IconVolume,
  IconVolumeOff,
} from '@tabler/icons-react';
import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import type { Video } from '../api/types';
import {
  clampTime,
  formatClock,
  formatTimecode,
  fpsValue,
  lastFrameIndex,
  nextRate,
  PLAYBACK_RATES,
  stepTime,
  thumbnailIndex,
  thumbnailUrl,
  timeToFrame,
  type Fps,
} from './frameMath';

interface VideoFrameMetadataLike {
  mediaTime: number;
}

/** requestVideoFrameCallback is not in every TypeScript DOM lib yet; type what we use. */
type RvfcVideoElement = HTMLVideoElement & {
  requestVideoFrameCallback?: (
    callback: (now: number, metadata: VideoFrameMetadataLike) => void,
  ) => number;
  cancelVideoFrameCallback?: (handle: number) => void;
  webkitRequestFullscreen?: () => void;
};

const SKIP_SECONDS = 5;

const SHORTCUTS: Array<[string, string]> = [
  ['Space or K', 'Play / pause'],
  ['L', 'Play faster (up to 2x)'],
  ['J', 'Play slower (down to 0.25x)'],
  ['→ or .', 'Next frame'],
  ['← or ,', 'Previous frame'],
  ['Shift + → / ←', `Forward / back ${SKIP_SECONDS} seconds`],
  ['↑ / ↓', 'Speed up / slow down'],
  ['Home / End', 'Start / end of video'],
  ['F', 'Full screen'],
  ['M', 'Mute'],
];

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

export function VideoPlayer({ video }: { video: Video }) {
  const fps = useMemo<Fps>(
    () => ({ num: video.fps_num ?? 30, den: video.fps_den ?? 1 }),
    [video.fps_num, video.fps_den],
  );
  const duration = video.duration_s ?? 0;
  const lastFrame = lastFrameIndex(duration, fps, video.frame_count);

  const videoRef = useRef<RvfcVideoElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLInputElement>(null);
  const timeRef = useRef(0);
  const seekTargetRef = useRef<number | null>(null);
  const wasPlayingRef = useRef(false);

  const [time, setTimeState] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [muted, setMuted] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [hover, setHover] = useState<{ x: number; t: number } | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);

  const setTime = useCallback((t: number) => {
    timeRef.current = t;
    setTimeState(t);
  }, []);

  // Frame-accurate clock: requestVideoFrameCallback reports the media time of the frame on
  // screen. Browsers without it fall back to polling currentTime every animation frame.
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    let cancelled = false;
    let handle = 0;
    let raf = 0;
    const hasRvfc = typeof el.requestVideoFrameCallback === 'function';
    if (hasRvfc) {
      const tick = (_now: number, meta: VideoFrameMetadataLike) => {
        if (cancelled) return;
        seekTargetRef.current = null;
        setTime(meta.mediaTime);
        handle = el.requestVideoFrameCallback!(tick);
      };
      handle = el.requestVideoFrameCallback!(tick);
    } else {
      const loop = () => {
        if (cancelled) return;
        setTime(el.currentTime);
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
    }
    const onSeeked = () => {
      seekTargetRef.current = null;
      setTime(el.currentTime);
    };
    el.addEventListener('seeked', onSeeked);
    return () => {
      cancelled = true;
      el.removeEventListener('seeked', onSeeked);
      if (hasRvfc) el.cancelVideoFrameCallback?.(handle);
      cancelAnimationFrame(raf);
    };
  }, [setTime, video.id]);

  // Mirror element state into React state.
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onRate = () => setRate(el.playbackRate);
    const onVolume = () => setMuted(el.muted);
    const onWaiting = () => setBuffering(true);
    const onReady = () => setBuffering(false);
    el.addEventListener('play', onPlay);
    el.addEventListener('pause', onPause);
    el.addEventListener('ended', onPause);
    el.addEventListener('ratechange', onRate);
    el.addEventListener('volumechange', onVolume);
    el.addEventListener('waiting', onWaiting);
    el.addEventListener('playing', onReady);
    el.addEventListener('canplay', onReady);
    el.addEventListener('seeked', onReady);
    return () => {
      el.removeEventListener('play', onPlay);
      el.removeEventListener('pause', onPause);
      el.removeEventListener('ended', onPause);
      el.removeEventListener('ratechange', onRate);
      el.removeEventListener('volumechange', onVolume);
      el.removeEventListener('waiting', onWaiting);
      el.removeEventListener('playing', onReady);
      el.removeEventListener('canplay', onReady);
      el.removeEventListener('seeked', onReady);
    };
  }, [video.id]);

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === rootRef.current);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const seekTo = useCallback(
    (t: number) => {
      const el = videoRef.current;
      if (!el) return;
      const target = clampTime(t, duration);
      seekTargetRef.current = target;
      el.currentTime = target;
      setTime(target);
    },
    [duration, setTime],
  );

  const currentBase = () => seekTargetRef.current ?? timeRef.current;

  const togglePlay = useCallback(() => {
    const el = videoRef.current;
    if (!el) return;
    if (el.paused) {
      if (el.ended || (duration > 0 && el.currentTime >= duration - 1e-3)) el.currentTime = 0;
      void el.play();
    } else {
      el.pause();
    }
  }, [duration]);

  const step = useCallback(
    (frames: number) => {
      const el = videoRef.current;
      if (!el) return;
      el.pause();
      seekTo(stepTime(currentBase(), frames, fps, duration, video.frame_count));
    },
    [duration, fps, seekTo, video.frame_count],
  );

  const skip = useCallback(
    (seconds: number) => seekTo(currentBase() + seconds),
    [seekTo],
  );

  const applyRate = useCallback((r: number) => {
    const el = videoRef.current;
    if (!el) return;
    el.playbackRate = r;
    setRate(r);
  }, []);

  const changeRate = useCallback(
    (direction: 1 | -1, startPlaying: boolean) => {
      const el = videoRef.current;
      if (!el) return;
      applyRate(nextRate(el.playbackRate, direction));
      if (startPlaying && el.paused) void el.play();
    },
    [applyRate],
  );

  const toggleMute = useCallback(() => {
    const el = videoRef.current;
    if (el) el.muted = !el.muted;
  }, []);

  const toggleFullscreen = useCallback(() => {
    const root = rootRef.current;
    const el = videoRef.current;
    if (!root || !el) return;
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else if (root.requestFullscreen) {
      void root.requestFullscreen();
    } else if (el.webkitRequestFullscreen) {
      el.webkitRequestFullscreen();
    }
  }, []);

  // Keyboard shortcuts, active while the player is on screen and focus is not in a text field.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || isTypingTarget(event.target)) return;
      let handled = true;
      switch (event.key) {
        case ' ':
        case 'k':
        case 'K':
          togglePlay();
          break;
        case 'l':
        case 'L':
          changeRate(1, true);
          break;
        case 'j':
        case 'J':
          changeRate(-1, true);
          break;
        case 'ArrowRight':
          if (event.shiftKey) skip(SKIP_SECONDS);
          else step(1);
          break;
        case 'ArrowLeft':
          if (event.shiftKey) skip(-SKIP_SECONDS);
          else step(-1);
          break;
        case '.':
          step(1);
          break;
        case ',':
          step(-1);
          break;
        case 'ArrowUp':
          changeRate(1, false);
          break;
        case 'ArrowDown':
          changeRate(-1, false);
          break;
        case 'Home':
          seekTo(0);
          break;
        case 'End':
          seekTo(stepTime(duration, 0, fps, duration, video.frame_count));
          break;
        case 'f':
        case 'F':
          toggleFullscreen();
          break;
        case 'm':
        case 'M':
          toggleMute();
          break;
        default:
          handled = false;
      }
      if (handled) event.preventDefault();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [changeRate, duration, fps, seekTo, skip, step, toggleFullscreen, toggleMute, togglePlay, video.frame_count]);

  // Seek bar.
  const onBarPointerDown = () => {
    const el = videoRef.current;
    if (!el) return;
    wasPlayingRef.current = !el.paused;
    el.pause();
  };
  const onBarPointerUp = () => {
    const el = videoRef.current;
    if (el && wasPlayingRef.current) void el.play();
    wasPlayingRef.current = false;
  };
  const onBarHover = (event: ReactMouseEvent<HTMLInputElement>) => {
    const bar = barRef.current;
    if (!bar || duration <= 0) return;
    const rect = bar.getBoundingClientRect();
    const fraction = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    setHover({ x: event.clientX - rect.left, t: fraction * duration });
  };

  const frame = timeToFrame(time, fps);
  const progressPercent = duration > 0 ? (time / duration) * 100 : 0;
  const thumbs =
    video.thumbnail_url_template && video.thumbnail_interval_s && video.thumbnail_count
      ? {
          template: video.thumbnail_url_template,
          interval: video.thumbnail_interval_s,
          count: video.thumbnail_count,
        }
      : null;

  return (
    <div ref={rootRef} className="player-root" data-testid="player">
      <Stack gap="sm">
        <div className="player-stage" onClick={togglePlay} onDoubleClick={toggleFullscreen}>
          <video
            ref={videoRef}
            src={video.proxy_url ?? undefined}
            poster={video.poster_url ?? undefined}
            preload="auto"
            playsInline
            data-testid="player-video"
          />
          {buffering && (
            <Loader
              color="white"
              size="lg"
              style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
            />
          )}
        </div>

        <div style={{ position: 'relative' }}>
          {hover && thumbs && (
            <div className="seek-thumb" style={{ left: hover.x }}>
              <img
                src={thumbnailUrl(thumbs.template, thumbnailIndex(hover.t, thumbs.interval, thumbs.count))}
                alt=""
              />
              <div>{formatClock(hover.t)}</div>
            </div>
          )}
          <input
            ref={barRef}
            type="range"
            className="seek-bar"
            min={0}
            max={duration || 0}
            step={1 / fpsValue(fps)}
            value={Math.min(time, duration || 0)}
            onChange={(e) => seekTo(Number(e.currentTarget.value))}
            onPointerDown={onBarPointerDown}
            onPointerUp={onBarPointerUp}
            onMouseMove={onBarHover}
            onMouseLeave={() => setHover(null)}
            aria-label="Seek"
            aria-valuetext={formatClock(time)}
            style={{ ['--seek-progress' as string]: `${progressPercent}%` }}
            data-testid="player-seek"
          />
        </div>

        <Group justify="space-between" wrap="wrap" gap="md">
          <Group gap="xs" wrap="nowrap">
            <Tooltip label={`Back ${SKIP_SECONDS} seconds (Shift + ←)`}>
              <ActionIcon size="xl" variant="light" onClick={() => skip(-SKIP_SECONDS)} aria-label={`Back ${SKIP_SECONDS} seconds`}>
                <IconRewindBackward5 size={26} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Previous frame (←)">
              <ActionIcon size="xl" variant="light" onClick={() => step(-1)} aria-label="Previous frame" data-testid="player-step-back">
                <IconPlayerSkipBack size={26} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Play / pause (Space or K)">
              <ActionIcon size={56} variant="filled" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'} data-testid="player-play">
                {playing ? <IconPlayerPause size={32} /> : <IconPlayerPlay size={32} />}
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Next frame (→)">
              <ActionIcon size="xl" variant="light" onClick={() => step(1)} aria-label="Next frame" data-testid="player-step-forward">
                <IconPlayerSkipForward size={26} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label={`Forward ${SKIP_SECONDS} seconds (Shift + →)`}>
              <ActionIcon size="xl" variant="light" onClick={() => skip(SKIP_SECONDS)} aria-label={`Forward ${SKIP_SECONDS} seconds`}>
                <IconRewindForward5 size={26} />
              </ActionIcon>
            </Tooltip>
          </Group>

          <Stack gap={0} align="center" className="readout">
            <Text fw={700} size="xl" data-testid="player-time">
              {formatClock(time, true)} <Text span c="dimmed" fw={400}>/ {formatClock(duration)}</Text>
            </Text>
            <Text size="sm" c="dimmed" data-testid="player-frame">
              Frame {frame} of {lastFrame + 1} · {formatTimecode(time, fps)} · {fpsValue(fps).toFixed(2)} fps
            </Text>
          </Stack>

          <Group gap="xs" wrap="nowrap">
            <Tooltip label="Playback speed (J slower, L faster)">
              <SegmentedControl
                size="sm"
                value={String(rate)}
                onChange={(v) => applyRate(Number(v))}
                data={PLAYBACK_RATES.map((r) => ({ value: String(r), label: `${r}x` }))}
                aria-label="Playback speed"
                data-testid="player-speed"
              />
            </Tooltip>
            <Tooltip label="Start (Home)">
              <ActionIcon size="lg" variant="subtle" onClick={() => seekTo(0)} aria-label="Go to start">
                <IconArrowBarToLeft size={22} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="End (End)">
              <ActionIcon size="lg" variant="subtle" onClick={() => seekTo(stepTime(duration, 0, fps, duration, video.frame_count))} aria-label="Go to end">
                <IconArrowBarToRight size={22} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label={muted ? 'Unmute (M)' : 'Mute (M)'}>
              <ActionIcon size="lg" variant="subtle" onClick={toggleMute} aria-label={muted ? 'Unmute' : 'Mute'}>
                {muted ? <IconVolumeOff size={22} /> : <IconVolume size={22} />}
              </ActionIcon>
            </Tooltip>
            <Tooltip label={fullscreen ? 'Exit full screen (F)' : 'Full screen (F)'}>
              <ActionIcon size="lg" variant="subtle" onClick={toggleFullscreen} aria-label="Full screen">
                {fullscreen ? <IconMinimize size={22} /> : <IconMaximize size={22} />}
              </ActionIcon>
            </Tooltip>
            <Popover opened={helpOpen} onChange={setHelpOpen} position="bottom-end" withArrow shadow="md">
              <Popover.Target>
                <Tooltip label="Keyboard shortcuts">
                  <ActionIcon size="lg" variant="subtle" onClick={() => setHelpOpen((o) => !o)} aria-label="Keyboard shortcuts">
                    <IconKeyboard size={22} />
                  </ActionIcon>
                </Tooltip>
              </Popover.Target>
              <Popover.Dropdown>
                <Table withRowBorders={false} verticalSpacing={4}>
                  <Table.Tbody>
                    {SHORTCUTS.map(([keys, what]) => (
                      <Table.Tr key={keys}>
                        <Table.Td>
                          <Kbd>{keys}</Kbd>
                        </Table.Td>
                        <Table.Td>{what}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Popover.Dropdown>
            </Popover>
          </Group>
        </Group>
      </Stack>
    </div>
  );
}
