"""Render a list of clips into one MP4 with FFmpeg: cut, normalise, caption, concatenate."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.services import ffmpeg

log = logging.getLogger(__name__)

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


@dataclass(frozen=True)
class ClipSpec:
    source: Path
    start_s: float
    end_s: float
    caption: str | None

    @property
    def duration_s(self) -> float:
        return max(0.1, self.end_s - self.start_s)


def find_font() -> Path | None:
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def _target_size(infos: list[ffmpeg.ProbeResult]) -> tuple[int, int]:
    return (1920, 1080) if any(i.height >= 1080 for i in infos) else (1280, 720)


def render(
    clips: list[ClipSpec],
    target: Path,
    settings: Settings,
    on_progress: Callable[[float, str], None] | None = None,
) -> None:
    if not clips:
        raise ValueError("Nothing to export.")
    work = target.parent / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    try:
        infos = [ffmpeg.probe(c.source, settings) for c in clips]
        width, height = _target_size(infos)
        fps = infos[0].fps
        font = find_font()
        if any(c.caption for c in clips) and font is None:
            log.warning("no font found for captions; exporting without them")
        segments: list[Path] = []
        total = len(clips)
        for index, (clip, info) in enumerate(zip(clips, infos, strict=True)):
            segment = work / f"seg_{index:04d}.mp4"
            filters = [
                f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                "setsar=1",
                "format=yuv420p",
            ]
            if clip.caption and font is not None:
                textfile = work / f"caption_{index:04d}.txt"
                textfile.write_text(clip.caption, encoding="utf-8")
                filters.append(
                    f"drawtext=fontfile={font}:textfile={textfile}:fontcolor=white"
                    f":fontsize={max(18, height // 27)}:box=1:boxcolor=black@0.55:boxborderw=12"
                    ":x=24:y=h-th-24"
                )
            cmd = [
                settings.ffmpeg_bin,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-v",
                "error",
                "-ss",
                f"{clip.start_s:.3f}",
                "-t",
                f"{clip.duration_s:.3f}",
                "-i",
                str(clip.source),
            ]
            if not info.has_audio:
                cmd += [
                    "-f",
                    "lavfi",
                    "-t",
                    f"{clip.duration_s:.3f}",
                    "-i",
                    "anullsrc=r=48000:cl=stereo",
                ]
            cmd += ["-map", "0:v:0", "-map", "0:a:0" if info.has_audio else "1:a:0"]
            cmd += [
                "-vf",
                ",".join(filters),
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-preset",
                settings.transcode_preset,
                "-crf",
                "20",
                "-profile:v",
                "high",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-af",
                "aresample=async=1",
                "-shortest",
                "-movflags",
                "+faststart",
                "-progress",
                "pipe:1",
                "-nostats",
                str(segment),
            ]

            def report(fraction: float, index: int = index) -> None:
                if on_progress:
                    on_progress(
                        (index + fraction) / total * 0.95, f"Rendering clip {index + 1} of {total}"
                    )

            ffmpeg.run_with_progress(cmd, clip.duration_s, report)
            segments.append(segment)

        if len(segments) == 1:
            shutil.move(str(segments[0]), str(target))
        else:
            listing = work / "list.txt"
            listing.write_text("".join(f"file '{s.name}'\n" for s in segments), encoding="utf-8")
            if on_progress:
                on_progress(0.96, "Joining clips")
            ffmpeg.run_with_progress(
                [
                    settings.ffmpeg_bin,
                    "-hide_banner",
                    "-nostdin",
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(listing),
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    "-progress",
                    "pipe:1",
                    "-nostats",
                    str(target),
                ],
                sum(c.duration_s for c in clips),
            )
    finally:
        shutil.rmtree(work, ignore_errors=True)
