"""FFmpeg and ffprobe wrappers: probing, proxy encoding with progress, poster and thumbnails."""

from __future__ import annotations

import json
import logging
import math
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

from app.config import Settings

log = logging.getLogger(__name__)


class FFmpegError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProbeResult:
    duration_s: float
    width: int
    height: int
    fps: Fraction
    frame_count: int | None
    video_codec: str | None
    has_audio: bool

    @property
    def fps_float(self) -> float:
        return float(self.fps)


def _parse_rate(value: str | None) -> Fraction | None:
    if not value or value in {"0/0", "0"}:
        return None
    try:
        frac = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return frac if frac > 0 else None


def probe(path: Path, settings: Settings) -> ProbeResult:
    """Read duration, size, frame rate (as an exact rational) and stream layout with ffprobe."""
    cmd = [
        settings.ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed: {result.stderr.strip()[:2000]}")
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise FFmpegError("The file has no video stream.")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    # avg_frame_rate is the true average; r_frame_rate is the container's nominal base rate.
    fps = _parse_rate(video.get("avg_frame_rate")) or _parse_rate(video.get("r_frame_rate"))
    if fps is None:
        raise FFmpegError("Could not read the frame rate of the file.")
    fps = fps.limit_denominator(1001)

    fmt = data.get("format", {})
    duration_raw = fmt.get("duration") or video.get("duration")
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError) as exc:
        raise FFmpegError("Could not read the duration of the file.") from exc

    frame_count: int | None = None
    nb = video.get("nb_frames")
    if nb and str(nb).isdigit():
        frame_count = int(nb)

    return ProbeResult(
        duration_s=duration,
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        fps=fps,
        frame_count=frame_count,
        video_codec=video.get("codec_name"),
        has_audio=has_audio,
    )


@lru_cache(maxsize=4)
def available_encoders(ffmpeg_bin: str) -> frozenset[str]:
    result = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-encoders"], capture_output=True, text=True, check=False
    )
    names = set(re.findall(r"^\s*V[\w.]{5}\s+(\S+)", result.stdout, flags=re.M))
    return frozenset(names)


def nvenc_usable(settings: Settings) -> bool:
    """True when h264_nvenc is both compiled in and can actually open a GPU session."""
    if "h264_nvenc" not in available_encoders(settings.ffmpeg_bin):
        return False
    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "nullsrc=s=256x256:d=0.1",
        "-c:v",
        "h264_nvenc",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
    return result.returncode == 0


def choose_encoder(settings: Settings) -> str:
    if settings.transcode_encoder == "libx264":
        return "libx264"
    if settings.transcode_encoder == "h264_nvenc":
        return "h264_nvenc"
    return "h264_nvenc" if nvenc_usable(settings) else "libx264"


def proxy_command(
    source: Path, target: Path, info: ProbeResult, settings: Settings, encoder: str
) -> list[str]:
    """Build the FFmpeg command for the browser proxy.

    H.264 High profile in yuv420p, AAC audio, constant frame rate equal to the source, a
    keyframe at least every second (GOP = fps, plus forced keyframes on each whole second),
    the moov atom at the front (faststart), and height capped at transcode_max_height.
    """
    gop = max(1, math.ceil(info.fps_float))
    scale = f"scale=-2:'min({settings.transcode_max_height},ih)'"
    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-v",
        "error",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-vf",
        f"{scale},format=yuv420p",
        "-fps_mode",
        "cfr",
        "-r",
        str(info.fps),
        "-g",
        str(gop),
        "-keyint_min",
        str(gop),
        "-sc_threshold",
        "0",
        "-force_key_frames",
        "expr:gte(t,n_forced*1)",
    ]
    if encoder == "h264_nvenc":
        cmd += ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0"]
    else:
        cmd += [
            "-c:v",
            "libx264",
            "-preset",
            settings.transcode_preset,
            "-crf",
            str(settings.transcode_crf),
        ]
    cmd += ["-profile:v", "high", "-level", "4.1"]
    if info.has_audio:
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "128k", "-ac", "2"]
    else:
        cmd += ["-an"]
    cmd += [
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(target),
    ]
    return cmd


_PROGRESS_LINE = re.compile(r"^(\w+)=(.*)$")


def run_with_progress(
    cmd: list[str], duration_s: float, on_progress: Callable[[float], None] | None = None
) -> None:
    """Run FFmpeg with `-progress pipe:1`, reporting a 0..1 fraction from out_time."""
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        match = _PROGRESS_LINE.match(line.strip())
        if not match or on_progress is None:
            continue
        key, value = match.groups()
        if key == "out_time_us" and value.lstrip("-").isdigit() and duration_s > 0:
            on_progress(min(1.0, max(0.0, int(value) / 1_000_000 / duration_s)))
        elif key == "progress" and value == "end":
            on_progress(1.0)
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise FFmpegError(f"ffmpeg failed ({proc.returncode}): {stderr.strip()[-2000:]}")


def make_poster(proxy: Path, target: Path, duration_s: float, settings: Settings) -> None:
    at = min(5.0, duration_s * 0.1) if duration_s > 1 else 0.0
    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{at:.3f}",
        "-i",
        str(proxy),
        "-frames:v",
        "1",
        "-vf",
        "scale=-2:'min(720,ih)'",
        "-q:v",
        "3",
        str(target),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FFmpegError(f"poster failed: {result.stderr.strip()[-2000:]}")


def make_thumbnails(
    proxy: Path,
    out_dir: Path,
    duration_s: float,
    settings: Settings,
    on_progress: Callable[[float], None] | None = None,
) -> int:
    """One JPEG every `thumbnail_interval_s` seconds plus a WebVTT index. Returns the count.

    The proxy has a keyframe every second, so the decoder is told to skip everything but
    keyframes (`-skip_frame nokey`): a 90-minute match then means decoding ~5,400 frames
    instead of ~160,000, which turns minutes into seconds. Each thumbnail is the keyframe
    nearest its slot, at most half a second from the exact time.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    interval = max(1, settings.thumbnail_interval_s)
    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-v",
        "error",
        "-skip_frame",
        "nokey",
        "-i",
        str(proxy),
        "-vf",
        f"fps=1/{interval},scale={settings.thumbnail_width}:-2",
        "-q:v",
        "5",
        "-progress",
        "pipe:1",
        "-nostats",
        str(out_dir / "%05d.jpg"),
    ]
    try:
        run_with_progress(cmd, duration_s, on_progress)
    except FFmpegError as exc:
        raise FFmpegError(f"thumbnails failed: {exc}") from exc
    files = sorted(out_dir.glob("*.jpg"))
    lines = ["WEBVTT", ""]
    for index, _file in enumerate(files, start=1):
        start = (index - 1) * interval
        end = min(duration_s, start + interval) if duration_s > 0 else start + interval
        lines += [f"{_vtt_time(start)} --> {_vtt_time(end)}", f"{index:05d}.jpg", ""]
    (out_dir / "thumbs.vtt").write_text("\n".join(lines), encoding="utf-8")
    return len(files)


def _vtt_time(seconds: float) -> str:
    whole = int(seconds)
    ms = round((seconds - whole) * 1000)
    h, rem = divmod(whole, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def generate_test_clip(
    target: Path,
    settings: Settings,
    *,
    duration_s: float = 30.0,
    fps: int = 30,
    size: str = "1280x720",
) -> None:
    """A synthetic clip from FFmpeg's testsrc (colour bars, moving box and a burnt-in clock)
    with a tone, so the app can be developed and tested without real footage."""
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size={size}:rate={fps}:duration={duration_s}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:sample_rate=48000:duration={duration_s}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(target),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FFmpegError(f"test clip failed: {result.stderr.strip()[-2000:]}")
