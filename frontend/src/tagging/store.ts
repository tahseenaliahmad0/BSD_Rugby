/**
 * The tag store for one match: local state, immediate saves, optimistic concurrency and an
 * undo/redo command stack (ADRs 0007 and 0008).
 *
 * Every change is a command with `apply` and `revert`, both of which call the API and update
 * the local state. Commands run one at a time in order. A 409 from the API means someone else
 * changed the tag: the store adopts the server's version, drops the command and reports it.
 */
import { ApiError } from '../api/client';
import type { Tag, TagConflict, TagCreate, TagUpdate } from '../api/types';

export interface TagApi {
  list(eventId: string): Promise<Tag[]>;
  create(eventId: string, body: TagCreate): Promise<Tag>;
  update(tagId: string, body: TagUpdate): Promise<Tag>;
  remove(tagId: string, version: number): Promise<void>;
  batch(eventId: string, body: { create: TagCreate[]; delete: { id: string; version?: number }[] }): Promise<{ created: Tag[]; deleted: string[] }>;
  split(tagId: string, version: number, atMs: number): Promise<{ left: Tag; right: Tag }>;
  merge(eventId: string, refs: { id: string; version: number }[]): Promise<Tag>;
}

export interface OpenSpan {
  tagId: string;
  code: string;
  startMs: number;
}

export interface TagStoreState {
  tags: ReadonlyMap<string, Tag>;
  /** Tag ids sorted by start time, then creation. */
  order: readonly string[];
  selected: ReadonlySet<string>;
  /** The tag that descriptor presses apply to when nothing is selected. */
  lastTagId: string | null;
  openSpans: ReadonlyMap<string, OpenSpan>;
  canUndo: boolean;
  canRedo: boolean;
  /** A message for the user: a conflict or a failed save. Cleared on the next action. */
  notice: string | null;
  loading: boolean;
  pending: number;
}

interface Command {
  label: string;
  apply(): Promise<void>;
  revert(): Promise<void>;
}

type Listener = () => void;

const MAX_STACK = 200;

function tagFields(tag: Tag): TagCreate {
  return {
    id: tag.id,
    template_id: tag.template_id,
    code: tag.code,
    start_ms: tag.start_ms,
    end_ms: tag.end_ms,
    descriptors: tag.descriptors,
    player_ids: tag.player_ids,
    note: tag.note,
  };
}

export function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  // Fallback for very old browsers: not cryptographically strong, only needs to be unique.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export class TagStore {
  private tags = new Map<string, Tag>();
  private order: string[] = [];
  private selected = new Set<string>();
  private lastTagId: string | null = null;
  private openSpans = new Map<string, OpenSpan>();
  private undoStack: Command[] = [];
  private redoStack: Command[] = [];
  private notice: string | null = null;
  private loading = true;
  private pending = 0;
  private listeners = new Set<Listener>();
  private snapshot: TagStoreState;
  private queue: Promise<void> = Promise.resolve();

  constructor(
    readonly eventId: string,
    private readonly api: TagApi,
  ) {
    this.snapshot = this.buildSnapshot();
  }

  // Subscription (useSyncExternalStore) -------------------------------------------------
  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): TagStoreState => this.snapshot;

  private buildSnapshot(): TagStoreState {
    return {
      tags: this.tags,
      order: this.order,
      selected: this.selected,
      lastTagId: this.lastTagId,
      openSpans: this.openSpans,
      canUndo: this.undoStack.length > 0,
      canRedo: this.redoStack.length > 0,
      notice: this.notice,
      loading: this.loading,
      pending: this.pending,
    };
  }

  private emit(): void {
    this.tags = new Map(this.tags);
    this.selected = new Set(this.selected);
    this.openSpans = new Map(this.openSpans);
    this.resort();
    this.snapshot = this.buildSnapshot();
    for (const listener of this.listeners) listener();
  }

  private resort(): void {
    this.order = [...this.tags.values()]
      .sort((a, b) => a.start_ms - b.start_ms || a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id))
      .map((t) => t.id);
  }

  // Loading -------------------------------------------------------------------------------
  async load(): Promise<void> {
    this.loading = true;
    this.emit();
    const tags = await this.api.list(this.eventId);
    this.tags = new Map(tags.map((t) => [t.id, t]));
    this.loading = false;
    this.emit();
  }

  setTags(tags: Tag[]): void {
    this.tags = new Map(tags.map((t) => [t.id, t]));
    this.loading = false;
    this.emit();
  }

  get(id: string): Tag | undefined {
    return this.tags.get(id);
  }

  // Selection -----------------------------------------------------------------------------
  select(ids: string[], additive = false): void {
    if (!additive) this.selected.clear();
    for (const id of ids) if (this.tags.has(id)) this.selected.add(id);
    if (ids.length === 1) this.lastTagId = ids[0];
    this.emit();
  }

  toggleSelect(id: string): void {
    if (this.selected.has(id)) this.selected.delete(id);
    else if (this.tags.has(id)) this.selected.add(id);
    this.lastTagId = id;
    this.emit();
  }

  clearSelection(): void {
    this.selected.clear();
    this.emit();
  }

  /** The tag descriptor presses apply to: the single selection, else the most recent tag. */
  targetTagId(): string | null {
    if (this.selected.size === 1) return [...this.selected][0];
    if (this.lastTagId && this.tags.has(this.lastTagId)) return this.lastTagId;
    return null;
  }

  clearNotice(): void {
    if (this.notice !== null) {
      this.notice = null;
      this.emit();
    }
  }

  // Commands ------------------------------------------------------------------------------
  private run(command: Command): Promise<void> {
    this.notice = null;
    this.redoStack = [];
    return this.execute(command, 'apply');
  }

  private execute(command: Command, direction: 'apply' | 'revert'): Promise<void> {
    const task = async () => {
      this.pending += 1;
      this.emit();
      try {
        if (direction === 'apply') await command.apply();
        else await command.revert();
        if (direction === 'apply') this.undoStack.push(command);
        else this.redoStack.push(command);
        if (this.undoStack.length > MAX_STACK) this.undoStack.shift();
      } catch (error) {
        this.handleError(error);
      } finally {
        this.pending -= 1;
        this.emit();
      }
    };
    this.queue = this.queue.then(task, task);
    return this.queue;
  }

  private handleError(error: unknown): void {
    if (error instanceof ApiError && error.status === 409) {
      this.notice = error.detail;
      const current = (error.body as TagConflict | undefined)?.current ?? null;
      if (current) this.tags.set(current.id, current);
      // We do not know which tag the stale copy was for a delete; a reload is the safe path.
      if (error.conflictTagId && !current) this.tags.delete(error.conflictTagId);
      return;
    }
    if (error instanceof ApiError && error.status === 404) {
      this.notice = 'That tag no longer exists. Someone else may have deleted it.';
      if (error.conflictTagId) this.tags.delete(error.conflictTagId);
      return;
    }
    this.notice = error instanceof Error ? error.message : 'Could not save the change.';
  }

  async undo(): Promise<void> {
    const command = this.undoStack.pop();
    if (!command) return;
    this.notice = null;
    await this.execute(command, 'revert');
  }

  async redo(): Promise<void> {
    const command = this.redoStack.pop();
    if (!command) return;
    this.notice = null;
    await this.execute(command, 'apply');
  }

  // Tag operations -------------------------------------------------------------------------
  createTag(body: TagCreate): Promise<void> {
    const id = body.id ?? newId();
    const payload = { ...body, id };
    return this.run({
      label: `Add ${body.code}`,
      apply: async () => {
        const tag = await this.api.create(this.eventId, payload);
        this.tags.set(tag.id, tag);
        this.lastTagId = tag.id;
        this.selected.clear();
      },
      revert: async () => {
        const tag = this.tags.get(id);
        if (tag) await this.api.remove(id, tag.version);
        this.tags.delete(id);
        this.selected.delete(id);
        this.openSpans.forEach((span, code) => {
          if (span.tagId === id) this.openSpans.delete(code);
        });
      },
    });
  }

  updateTag(id: string, patch: Omit<TagUpdate, 'version'>): Promise<void> {
    const before = this.tags.get(id);
    if (!before) return Promise.resolve();
    const previous = tagFields(before);
    return this.run({
      label: `Change ${before.code}`,
      apply: async () => {
        const current = this.tags.get(id);
        if (!current) throw tagGone(id);
        const updated = await this.api.update(id, { ...patch, version: current.version }).catch(rethrowWith(id));
        this.tags.set(id, updated);
      },
      revert: async () => {
        const current = this.tags.get(id);
        if (!current) throw tagGone(id);
        const restored = await this.api
          .update(id, {
            version: current.version,
            code: previous.code,
            start_ms: previous.start_ms,
            end_ms: previous.end_ms,
            descriptors: previous.descriptors,
            player_ids: previous.player_ids,
            note: previous.note,
          })
          .catch(rethrowWith(id));
        this.tags.set(id, restored);
      },
    });
  }

  deleteTags(ids: string[]): Promise<void> {
    const snapshots = ids.map((id) => this.tags.get(id)).filter((t): t is Tag => t !== undefined);
    if (snapshots.length === 0) return Promise.resolve();
    return this.run({
      label: snapshots.length === 1 ? `Delete ${snapshots[0].code}` : `Delete ${snapshots.length} tags`,
      apply: async () => {
        const refs = snapshots
          .map((s) => this.tags.get(s.id))
          .filter((t): t is Tag => t !== undefined)
          .map((t) => ({ id: t.id, version: t.version }));
        await this.api.batch(this.eventId, { create: [], delete: refs });
        for (const ref of refs) {
          this.tags.delete(ref.id);
          this.selected.delete(ref.id);
          this.openSpans.forEach((span, code) => {
            if (span.tagId === ref.id) this.openSpans.delete(code);
          });
        }
      },
      revert: async () => {
        const result = await this.api.batch(this.eventId, { create: snapshots.map(tagFields), delete: [] });
        for (const tag of result.created) this.tags.set(tag.id, tag);
      },
    });
  }

  splitTag(id: string, atMs: number): Promise<void> {
    const before = this.tags.get(id);
    if (!before || !(before.start_ms < atMs && atMs < before.end_ms)) return Promise.resolve();
    let rightId: string | null = null;
    const previousEnd = before.end_ms;
    return this.run({
      label: `Split ${before.code}`,
      apply: async () => {
        const current = this.tags.get(id);
        if (!current) throw tagGone(id);
        const { left, right } = await this.api.split(id, current.version, atMs).catch(rethrowWith(id));
        rightId = right.id;
        this.tags.set(left.id, left);
        this.tags.set(right.id, right);
        this.selected.clear();
        this.selected.add(left.id);
        this.lastTagId = left.id;
      },
      revert: async () => {
        const current = this.tags.get(id);
        if (!current) throw tagGone(id);
        const right = rightId ? this.tags.get(rightId) : undefined;
        await this.api.batch(this.eventId, {
          create: [],
          delete: right ? [{ id: right.id, version: right.version }] : [],
        });
        if (right) this.tags.delete(right.id);
        const restored = await this.api.update(id, { version: current.version, end_ms: previousEnd }).catch(rethrowWith(id));
        this.tags.set(id, restored);
      },
    });
  }

  mergeTags(ids: string[]): Promise<void> {
    const snapshots = ids.map((id) => this.tags.get(id)).filter((t): t is Tag => t !== undefined);
    if (snapshots.length < 2) return Promise.resolve();
    let mergedId: string | null = null;
    return this.run({
      label: `Merge ${snapshots.length} tags`,
      apply: async () => {
        const refs = snapshots
          .map((s) => this.tags.get(s.id))
          .filter((t): t is Tag => t !== undefined)
          .map((t) => ({ id: t.id, version: t.version }));
        const merged = await this.api.merge(this.eventId, refs);
        mergedId = merged.id;
        for (const ref of refs) this.tags.delete(ref.id);
        this.tags.set(merged.id, merged);
        this.selected.clear();
        this.selected.add(merged.id);
        this.lastTagId = merged.id;
      },
      revert: async () => {
        const merged = mergedId ? this.tags.get(mergedId) : undefined;
        const result = await this.api.batch(this.eventId, {
          create: snapshots.map(tagFields),
          delete: merged ? [{ id: merged.id, version: merged.version }] : [],
        });
        if (merged) this.tags.delete(merged.id);
        for (const tag of result.created) this.tags.set(tag.id, tag);
      },
    });
  }

  // Spans -----------------------------------------------------------------------------------
  isOpen(code: string): boolean {
    return this.openSpans.has(code);
  }

  async openSpan(code: string, body: TagCreate): Promise<void> {
    const id = body.id ?? newId();
    await this.createTag({ ...body, id });
    if (this.tags.has(id)) {
      this.openSpans.set(code, { tagId: id, code, startMs: body.start_ms });
      this.emit();
    }
  }

  async closeSpan(code: string, endMs: number): Promise<void> {
    const span = this.openSpans.get(code);
    if (!span) return;
    this.openSpans.delete(code);
    this.emit();
    await this.updateTag(span.tagId, { end_ms: endMs });
  }

  async closeAllSpans(endMs: number): Promise<void> {
    for (const code of [...this.openSpans.keys()]) await this.closeSpan(code, endMs);
  }
}

function tagGone(id: string): ApiError {
  const error = new ApiError(404, 'That tag no longer exists.');
  error.conflictTagId = id;
  return error;
}

function rethrowWith(id: string): (error: unknown) => never {
  return (error: unknown) => {
    if (error instanceof ApiError) error.conflictTagId = id;
    throw error;
  };
}
