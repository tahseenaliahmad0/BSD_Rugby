/**
 * Canvas timeline: one row per code, zoom and scroll, playhead, click to seek and select,
 * drag bodies and edges with frame snapping, marquee multi-select. Drawing on a canvas keeps
 * a full match of tags (1,500+) smooth: nothing in the DOM per tag.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { Tag } from '../api/types';
import type { Fps } from '../player/frameMath';
import type { OpenSpan } from './store';
import { formatMs, snapEventMsToFrame } from './time';

export interface TimelineRow {
  code: string;
  label: string;
  colour: string;
}

export interface TimelineProps {
  tags: ReadonlyMap<string, Tag>;
  order: readonly string[];
  rows: TimelineRow[];
  selected: ReadonlySet<string>;
  openSpans: ReadonlyMap<string, OpenSpan>;
  playheadMs: number;
  /** End of the timeline in event milliseconds (video offset + duration). */
  endMs: number;
  offsetMs: number;
  fps: Fps;
  following: boolean;
  onSeek: (ms: number) => void;
  onSelect: (ids: string[], additive: boolean) => void;
  onMove: (id: string, startMs: number, endMs: number) => void;
  onOpenTag?: (id: string) => void;
}

const GUTTER = 128;
const RULER = 26;
const ROW_H = 30;
const TAG_PAD = 5;
const HANDLE_PX = 7;
const MIN_TAG_MS = 100;
const MIN_PX_PER_MS = 0.0005; // whole 90 min match in ~2700 px
const MAX_PX_PER_MS = 0.4; // 2.5 ms per px, frame level

type DragMode = 'move' | 'start' | 'end' | 'marquee' | 'scrub';

interface Drag {
  mode: DragMode;
  id?: string;
  originX: number;
  originY: number;
  originMs: number;
  origStart: number;
  origEnd: number;
  additive: boolean;
  moved: boolean;
  currentStart: number;
  currentEnd: number;
  marqueeTo?: { x: number; y: number };
}

export function Timeline(props: TimelineProps) {
  const { tags, order, rows, selected, openSpans, playheadMs, endMs, offsetMs, fps, following, onSeek, onSelect, onMove, onOpenTag } = props;
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(800);
  const [view, setView] = useState({ startMs: 0, pxPerMs: 0.02 });
  const [hoverId, setHoverId] = useState<string | null>(null);
  // The drag lives in a ref (read by pointer handlers); a tick re-renders the canvas.
  const dragRef = useRef<Drag | null>(null);
  const [dragTick, setDragTick] = useState(0);
  const [dragging, setDragging] = useState(false);
  const setDrag = useCallback((next: Drag | null) => {
    dragRef.current = next;
    setDragging(next !== null);
    setDragTick((t) => t + 1);
  }, []);
  const fittedRef = useRef(false);

  const rowIndex = useMemo(() => new Map(rows.map((r, i) => [r.code, i])), [rows]);
  const height = RULER + Math.max(rows.length, 1) * ROW_H + 8;
  const trackWidth = Math.max(1, width - GUTTER);

  // Measure the container; the first measurement also fits the whole match into view.
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth;
      setWidth(w);
      if (!fittedRef.current && w > 0) {
        fittedRef.current = true;
        setView({ startMs: 0, pxPerMs: Math.max(MIN_PX_PER_MS, (w - GUTTER) / Math.max(endMs, 60_000)) });
      }
    };
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    measure();
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const msToX = useCallback((ms: number) => GUTTER + (ms - view.startMs) * view.pxPerMs, [view]);
  const xToMs = useCallback((x: number) => view.startMs + (x - GUTTER) / view.pxPerMs, [view]);
  const visibleMs = trackWidth / view.pxPerMs;

  // Follow the playhead while playing (state adjusted during render, as React recommends
  // for values derived from props; it re-renders once before painting).
  if (following && !dragging && (playheadMs < view.startMs || playheadMs > view.startMs + visibleMs)) {
    setView({ ...view, startMs: Math.max(0, playheadMs - visibleMs * 0.2) });
  }

  const clampView = useCallback(
    (startMs: number, pxPerMs: number) => {
      const px = Math.min(MAX_PX_PER_MS, Math.max(MIN_PX_PER_MS, pxPerMs));
      const maxStart = Math.max(0, endMs - trackWidth / px + 2000);
      return { startMs: Math.min(maxStart, Math.max(0, startMs)), pxPerMs: px };
    },
    [endMs, trackWidth],
  );

  const zoomAt = useCallback(
    (factor: number, anchorX?: number) => {
      setView((v) => {
        const anchor = anchorX ?? GUTTER + trackWidth / 2;
        const anchorMs = v.startMs + (anchor - GUTTER) / v.pxPerMs;
        const px = v.pxPerMs * factor;
        return clampView(anchorMs - (anchor - GUTTER) / px, px);
      });
    },
    [clampView, trackWidth],
  );

  // Wheel: zoom with Ctrl/Cmd (and trackpad pinch), otherwise scroll horizontally.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      if (event.ctrlKey || event.metaKey) {
        zoomAt(Math.exp(-event.deltaY * 0.01), event.clientX - rect.left);
      } else {
        const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
        setView((v) => clampView(v.startMs + delta / v.pxPerMs, v.pxPerMs));
      }
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [clampView, zoomAt]);

  // Hit testing ---------------------------------------------------------------------------
  const hit = useCallback(
    (x: number, y: number): { id: string; part: 'start' | 'end' | 'body' } | null => {
      if (x < GUTTER || y < RULER) return null;
      const row = Math.floor((y - RULER) / ROW_H);
      if (row < 0 || row >= rows.length) return null;
      const code = rows[row].code;
      // Walk from the top-most drawn (latest in order) so overlapping tags pick the visible one.
      for (let i = order.length - 1; i >= 0; i--) {
        const tag = tags.get(order[i]);
        if (!tag || tag.code !== code) continue;
        const span = openSpans.get(tag.code);
        const end = span && span.tagId === tag.id ? Math.max(tag.end_ms, playheadMs) : tag.end_ms;
        const x1 = msToX(tag.start_ms);
        const x2 = msToX(end);
        if (x < x1 - 2 || x > x2 + 2) continue;
        if (x2 - x1 > HANDLE_PX * 3) {
          if (x <= x1 + HANDLE_PX) return { id: tag.id, part: 'start' };
          if (x >= x2 - HANDLE_PX) return { id: tag.id, part: 'end' };
        }
        return { id: tag.id, part: 'body' };
      }
      return null;
    },
    [msToX, openSpans, order, playheadMs, rows, tags],
  );

  const snap = useCallback((ms: number) => snapEventMsToFrame(Math.max(0, Math.min(endMs, ms)), offsetMs, fps), [endMs, fps, offsetMs]);

  // Pointer handling ----------------------------------------------------------------------
  const onPointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (event.button !== 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    event.currentTarget.setPointerCapture(event.pointerId);
    const additive = event.shiftKey || event.metaKey || event.ctrlKey;
    if (y < RULER && x >= GUTTER) {
      const ms = snap(xToMs(x));
      onSeek(ms);
      setDrag({ mode: 'scrub', originX: x, originY: y, originMs: ms, origStart: 0, origEnd: 0, additive: false, moved: false, currentStart: 0, currentEnd: 0 });
      return;
    }
    const target = hit(x, y);
    if (target) {
      const tag = tags.get(target.id)!;
      if (additive) onSelect([target.id], true);
      else if (!selected.has(target.id)) onSelect([target.id], false);
      setDrag({
        mode: target.part === 'body' ? 'move' : target.part,
        id: target.id,
        originX: x,
        originY: y,
        originMs: xToMs(x),
        origStart: tag.start_ms,
        origEnd: tag.end_ms,
        additive,
        moved: false,
        currentStart: tag.start_ms,
        currentEnd: tag.end_ms,
      });
      return;
    }
    if (x >= GUTTER) {
      if (!additive) onSelect([], false);
      setDrag({ mode: 'marquee', originX: x, originY: y, originMs: xToMs(x), origStart: 0, origEnd: 0, additive, moved: false, currentStart: 0, currentEnd: 0, marqueeTo: { x, y } });
    }
  };

  const onPointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const current = dragRef.current;
    if (!current) {
      const target = hit(x, y);
      setHoverId(target?.id ?? null);
      event.currentTarget.style.cursor = target ? (target.part === 'body' ? 'grab' : 'ew-resize') : y < RULER && x >= GUTTER ? 'text' : 'default';
      return;
    }
    const deltaMs = (x - current.originX) / view.pxPerMs;
    const moved = current.moved || Math.abs(x - current.originX) > 3 || Math.abs(y - current.originY) > 3;
    if (current.mode === 'scrub') {
      onSeek(snap(xToMs(x)));
      return;
    }
    if (current.mode === 'marquee') {
      setDrag({ ...current, moved, marqueeTo: { x, y } });
      return;
    }
    let start = current.origStart;
    let end = current.origEnd;
    if (current.mode === 'move') {
      const length = end - start;
      start = snap(current.origStart + deltaMs);
      end = start + length;
      if (end > endMs) {
        end = endMs;
        start = end - length;
      }
    } else if (current.mode === 'start') {
      start = Math.min(snap(current.origStart + deltaMs), end - MIN_TAG_MS);
    } else {
      end = Math.max(snap(current.origEnd + deltaMs), start + MIN_TAG_MS);
    }
    setDrag({ ...current, moved, currentStart: Math.max(0, start), currentEnd: end });
  };

  const onPointerUp = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const current = dragRef.current;
    if (!current) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    setDrag(null);
    if (current.mode === 'scrub') return;
    if (current.mode === 'marquee') {
      if (current.moved && current.marqueeTo) {
        const x1 = Math.min(current.originX, current.marqueeTo.x);
        const x2 = Math.max(current.originX, current.marqueeTo.x);
        const y1 = Math.min(current.originY, current.marqueeTo.y);
        const y2 = Math.max(current.originY, current.marqueeTo.y);
        const msA = xToMs(x1);
        const msB = xToMs(x2);
        const ids: string[] = [];
        for (const id of order) {
          const tag = tags.get(id);
          if (!tag) continue;
          const row = rowIndex.get(tag.code);
          if (row === undefined) continue;
          const top = RULER + row * ROW_H;
          if (top + ROW_H < y1 || top > y2) continue;
          if (tag.end_ms < msA || tag.start_ms > msB) continue;
          ids.push(id);
        }
        onSelect(ids, current.additive);
      }
      return;
    }
    if (current.id && current.moved) {
      if (current.currentStart !== current.origStart || current.currentEnd !== current.origEnd) {
        onMove(current.id, Math.round(current.currentStart), Math.round(current.currentEnd));
      }
    } else if (current.id && !current.additive) {
      const tag = tags.get(current.id);
      if (tag) onSeek(tag.start_ms);
    }
  };

  const onDoubleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const target = hit(event.clientX - rect.left, event.clientY - rect.top);
    if (target && onOpenTag) onOpenTag(target.id);
  };

  // Drawing ---------------------------------------------------------------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
    const colours = dark
      ? { bg: '#1a1b1e', row: '#212226', rowAlt: '#1d1e22', text: '#c1c2c5', grid: '#2c2e33', gutter: '#141517', ruler: '#25262b', playhead: '#ff6b6b', select: '#ffd43b', marquee: 'rgba(77, 171, 247, 0.25)' }
      : { bg: '#ffffff', row: '#f8f9fa', rowAlt: '#ffffff', text: '#343a40', grid: '#dee2e6', gutter: '#f1f3f5', ruler: '#e9ecef', playhead: '#e03131', select: '#f08c00', marquee: 'rgba(34, 139, 230, 0.2)' };

    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, width, height);

    // Rows
    rows.forEach((_, i) => {
      const top = RULER + i * ROW_H;
      ctx.fillStyle = i % 2 ? colours.rowAlt : colours.row;
      ctx.fillRect(GUTTER, top, trackWidth, ROW_H);
    });

    // Ruler ticks
    const step = chooseTickMs(view.pxPerMs);
    ctx.fillStyle = colours.ruler;
    ctx.fillRect(GUTTER, 0, trackWidth, RULER);
    ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textBaseline = 'middle';
    const firstTick = Math.floor(view.startMs / step) * step;
    for (let ms = firstTick; ms <= view.startMs + visibleMs; ms += step) {
      const x = msToX(ms);
      if (x < GUTTER) continue;
      ctx.strokeStyle = colours.grid;
      ctx.beginPath();
      ctx.moveTo(x, RULER - 8);
      ctx.lineTo(x, height);
      ctx.stroke();
      ctx.fillStyle = colours.text;
      ctx.fillText(formatMs(ms), x + 4, RULER / 2);
    }

    // Tags
    ctx.save();
    ctx.beginPath();
    ctx.rect(GUTTER, RULER, trackWidth, height - RULER);
    ctx.clip();
    const current = dragRef.current;
    for (const id of order) {
      const tag = tags.get(id);
      if (!tag) continue;
      const row = rowIndex.get(tag.code);
      if (row === undefined) continue;
      let start = tag.start_ms;
      let end = tag.end_ms;
      const span = openSpans.get(tag.code);
      const isOpen = span !== undefined && span.tagId === tag.id;
      if (isOpen) end = Math.max(end, playheadMs);
      if (current && current.id === id && current.moved) {
        start = current.currentStart;
        end = current.currentEnd;
      }
      const x1 = msToX(start);
      const x2 = msToX(end);
      if (x2 < GUTTER || x1 > width) continue;
      const top = RULER + row * ROW_H + TAG_PAD;
      const h = ROW_H - TAG_PAD * 2;
      const w = Math.max(2, x2 - x1);
      ctx.fillStyle = rows[row].colour;
      ctx.globalAlpha = hoverId === id ? 1 : 0.9;
      roundRect(ctx, x1, top, w, h, 4);
      ctx.fill();
      ctx.globalAlpha = 1;
      if (isOpen) {
        ctx.setLineDash([4, 3]);
        ctx.strokeStyle = colours.playhead;
        ctx.lineWidth = 2;
        roundRect(ctx, x1, top, w, h, 4);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      if (selected.has(id)) {
        ctx.strokeStyle = colours.select;
        ctx.lineWidth = 3;
        roundRect(ctx, x1 - 1, top - 1, w + 2, h + 2, 5);
        ctx.stroke();
      }
      if (w > 28) {
        ctx.fillStyle = '#fff';
        ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        const label = isOpen ? `${rows[row].label} (recording)` : tag.note ? `${rows[row].label} · ${tag.note}` : descriptorSummary(tag) || rows[row].label;
        ctx.fillText(ellipsis(ctx, label, w - 8), x1 + 5, top + h / 2);
      }
    }
    // Marquee
    if (current?.mode === 'marquee' && current.moved && current.marqueeTo) {
      ctx.fillStyle = colours.marquee;
      ctx.fillRect(Math.min(current.originX, current.marqueeTo.x), Math.min(current.originY, current.marqueeTo.y), Math.abs(current.marqueeTo.x - current.originX), Math.abs(current.marqueeTo.y - current.originY));
    }
    ctx.restore();

    // Playhead
    const px = msToX(playheadMs);
    if (px >= GUTTER && px <= width) {
      ctx.strokeStyle = colours.playhead;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, height);
      ctx.stroke();
      ctx.fillStyle = colours.playhead;
      ctx.beginPath();
      ctx.moveTo(px - 6, 0);
      ctx.lineTo(px + 6, 0);
      ctx.lineTo(px, 8);
      ctx.closePath();
      ctx.fill();
    }

    // Gutter with row labels (drawn last so it covers tags scrolled under it)
    ctx.fillStyle = colours.gutter;
    ctx.fillRect(0, 0, GUTTER, height);
    ctx.fillStyle = colours.text;
    ctx.font = 'bold 13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    rows.forEach((row, i) => {
      const top = RULER + i * ROW_H;
      ctx.fillStyle = row.colour;
      ctx.fillRect(8, top + 9, 6, ROW_H - 18);
      ctx.fillStyle = colours.text;
      ctx.fillText(ellipsis(ctx, row.label, GUTTER - 28), 20, top + ROW_H / 2);
    });
    ctx.fillStyle = colours.text;
    ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(formatMs(playheadMs, true), 8, RULER / 2);
  }, [dragTick, height, hoverId, msToX, openSpans, order, playheadMs, rowIndex, rows, selected, tags, trackWidth, view.pxPerMs, view.startMs, visibleMs, width]);

  return (
    <div ref={containerRef} className="timeline" data-testid="timeline" style={{ position: 'relative', width: '100%', overflow: 'hidden', userSelect: 'none', touchAction: 'none' }}>
      <canvas
        ref={canvasRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={onDoubleClick}
        role="img"
        aria-label="Tag timeline"
      />
      <TimelineZoom onZoomIn={() => zoomAt(1.6)} onZoomOut={() => zoomAt(1 / 1.6)} onFit={() => setView(clampView(0, Math.max(MIN_PX_PER_MS, trackWidth / Math.max(endMs, 60_000))))} />
    </div>
  );
}

function TimelineZoom({ onZoomIn, onZoomOut, onFit }: { onZoomIn: () => void; onZoomOut: () => void; onFit: () => void }) {
  return (
    <div style={{ position: 'absolute', right: 8, top: 2, display: 'flex', gap: 4 }}>
      <button type="button" className="tl-btn" onClick={onZoomOut} aria-label="Zoom out" title="Zoom out (Ctrl + scroll)">−</button>
      <button type="button" className="tl-btn" onClick={onZoomIn} aria-label="Zoom in" title="Zoom in (Ctrl + scroll)">+</button>
      <button type="button" className="tl-btn" onClick={onFit} aria-label="Fit whole match" title="Fit the whole match">Fit</button>
    </div>
  );
}

function chooseTickMs(pxPerMs: number): number {
  const steps = [1000, 2000, 5000, 10_000, 15_000, 30_000, 60_000, 120_000, 300_000, 600_000, 900_000, 1_800_000];
  for (const step of steps) if (step * pxPerMs >= 80) return step;
  return steps[steps.length - 1];
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function ellipsis(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let cut = text;
  while (cut.length > 1 && ctx.measureText(`${cut}…`).width > maxWidth) cut = cut.slice(0, -1);
  return cut.length > 1 ? `${cut}…` : '';
}

function descriptorSummary(tag: Tag): string {
  const parts: string[] = [];
  for (const value of Object.values(tag.descriptors)) {
    if (Array.isArray(value)) parts.push(...value);
    else if (value) parts.push(value);
  }
  return parts.length ? `${tag.code} · ${parts.join(', ')}` : '';
}
