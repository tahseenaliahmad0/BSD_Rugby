import { describe, expect, it } from 'vitest';
import { ApiError } from '../api/client';
import type { Tag, TagCreate, TagUpdate } from '../api/types';
import { TagStore, type TagApi } from './store';

/** An in-memory server that enforces versions like the real API. */
class FakeApi implements TagApi {
  tags = new Map<string, Tag>();
  calls: string[] = [];
  private seq = 0;

  private make(eventId: string, body: TagCreate): Tag {
    const id = body.id ?? `t${++this.seq}`;
    if (this.tags.has(id)) throw new ApiError(400, 'A tag with that id already exists.');
    const tag: Tag = {
      id, event_id: eventId, template_id: body.template_id ?? null, code: body.code,
      start_ms: body.start_ms, end_ms: body.end_ms, descriptors: body.descriptors ?? {},
      player_ids: body.player_ids ?? [], note: body.note ?? null, source: 'manual', version: 1,
      created_by: null, updated_by: null, created_at: String(++this.seq).padStart(6, '0'), updated_at: '',
    };
    this.tags.set(id, tag);
    return tag;
  }

  private check(id: string, version: number | undefined): Tag {
    const tag = this.tags.get(id);
    if (!tag) throw new ApiError(404, 'Not found.');
    if (version !== undefined && tag.version !== version) {
      throw new ApiError(409, 'This tag was changed by someone else.', { detail: 'x', current: tag });
    }
    return tag;
  }

  /** Simulate another user's edit. */
  externalEdit(id: string, patch: Partial<Tag>): void {
    const tag = this.tags.get(id)!;
    this.tags.set(id, { ...tag, ...patch, version: tag.version + 1 });
  }

  async list(): Promise<Tag[]> { this.calls.push('list'); return [...this.tags.values()]; }
  async create(eventId: string, body: TagCreate): Promise<Tag> { this.calls.push('create'); return this.make(eventId, body); }
  async update(tagId: string, body: TagUpdate): Promise<Tag> {
    this.calls.push('update');
    const tag = this.check(tagId, body.version);
    const patch: Partial<TagUpdate> = { ...body };
    delete patch.version;
    const updated: Tag = { ...tag, ...Object.fromEntries(Object.entries(patch).filter(([, v]) => v !== undefined)), version: tag.version + 1 } as Tag;
    this.tags.set(tagId, updated);
    return updated;
  }
  async remove(tagId: string, version: number): Promise<void> { this.calls.push('remove'); this.check(tagId, version); this.tags.delete(tagId); }
  async batch(eventId: string, body: { create: TagCreate[]; delete: { id: string; version?: number }[] }) {
    this.calls.push('batch');
    for (const ref of body.delete) { this.check(ref.id, ref.version); this.tags.delete(ref.id); }
    return { created: body.create.map((c) => this.make(eventId, c)), deleted: body.delete.map((d) => d.id) };
  }
  async split(tagId: string, version: number, atMs: number) {
    this.calls.push('split');
    const tag = this.check(tagId, version);
    const left = { ...tag, end_ms: atMs, version: tag.version + 1 };
    this.tags.set(tagId, left);
    const right = this.make(tag.event_id, { code: tag.code, start_ms: atMs, end_ms: tag.end_ms, descriptors: tag.descriptors, player_ids: tag.player_ids, note: tag.note });
    return { left, right };
  }
  async merge(_eventId: string, refs: { id: string; version: number }[]) {
    this.calls.push('merge');
    const tags = refs.map((r) => this.check(r.id, r.version)).sort((a, b) => a.start_ms - b.start_ms);
    const [keep, ...others] = tags;
    const merged = { ...keep, start_ms: Math.min(...tags.map((t) => t.start_ms)), end_ms: Math.max(...tags.map((t) => t.end_ms)), version: keep.version + 1 };
    this.tags.set(keep.id, merged);
    for (const o of others) this.tags.delete(o.id);
    return merged;
  }
}

async function setup() {
  const api = new FakeApi();
  const store = new TagStore('e1', api);
  await store.load();
  return { api, store };
}

const scrum = (start: number): TagCreate => ({ code: 'Scrum', start_ms: start, end_ms: start + 5000 });

describe('TagStore commands and undo/redo', () => {
  it('creates, undoes (delete) and redoes (re-create with the same id)', async () => {
    const { api, store } = await setup();
    await store.createTag(scrum(1000));
    const id = store.getSnapshot().order[0];
    expect(api.tags.has(id)).toBe(true);
    expect(store.getSnapshot().lastTagId).toBe(id);
    await store.undo();
    expect(api.tags.size).toBe(0);
    expect(store.getSnapshot().tags.size).toBe(0);
    expect(store.getSnapshot().canRedo).toBe(true);
    await store.redo();
    expect(api.tags.has(id)).toBe(true);
    expect(store.getSnapshot().order).toEqual([id]);
  });

  it('updates with the current version and reverts to the snapshot', async () => {
    const { api, store } = await setup();
    await store.createTag({ ...scrum(1000), descriptors: { outcome: 'Won' }, note: 'first' });
    const id = store.getSnapshot().order[0];
    await store.updateTag(id, { end_ms: 9000, descriptors: { outcome: 'Lost' }, note: null });
    expect(api.tags.get(id)).toMatchObject({ end_ms: 9000, descriptors: { outcome: 'Lost' }, note: null, version: 2 });
    await store.undo();
    expect(api.tags.get(id)).toMatchObject({ end_ms: 6000, descriptors: { outcome: 'Won' }, note: 'first', version: 3 });
    await store.redo();
    expect(api.tags.get(id)).toMatchObject({ end_ms: 9000, version: 4 });
  });

  it('deletes several tags in one batch and restores them with their ids on undo', async () => {
    const { api, store } = await setup();
    await store.createTag(scrum(1000));
    await store.createTag(scrum(2000));
    await store.createTag(scrum(3000));
    const ids = [...store.getSnapshot().order];
    await store.deleteTags(ids.slice(0, 2));
    expect([...api.tags.keys()]).toEqual([ids[2]]);
    expect(api.calls.filter((c) => c === 'batch')).toHaveLength(1);
    await store.undo();
    expect(new Set(api.tags.keys())).toEqual(new Set(ids));
    expect(store.getSnapshot().order).toEqual(ids);
  });

  it('splits and merges with full undo', async () => {
    const { api, store } = await setup();
    await store.createTag(scrum(1000));
    const id = store.getSnapshot().order[0];
    await store.splitTag(id, 3000);
    expect(store.getSnapshot().order).toHaveLength(2);
    const rightId = store.getSnapshot().order[1];
    expect(api.tags.get(id)?.end_ms).toBe(3000);
    expect(api.tags.get(rightId)).toMatchObject({ start_ms: 3000, end_ms: 6000 });
    await store.undo();
    expect(store.getSnapshot().order).toEqual([id]);
    expect(api.tags.get(id)?.end_ms).toBe(6000);

    await store.createTag(scrum(8000));
    const second = store.getSnapshot().order[1];
    await store.mergeTags([id, second]);
    expect(store.getSnapshot().order).toEqual([id]);
    expect(api.tags.get(id)).toMatchObject({ start_ms: 1000, end_ms: 13000 });
    expect(api.tags.has(second)).toBe(false);
    await store.undo();
    expect(store.getSnapshot().order).toEqual([id, second]);
    expect(api.tags.get(id)?.end_ms).toBe(6000);
    expect(api.tags.get(second)).toMatchObject({ start_ms: 8000, end_ms: 13000 });
    await store.redo();
    expect(store.getSnapshot().order).toEqual([id]);
  });

  it('reports a conflict, adopts the other person\'s version and drops the command', async () => {
    const { api, store } = await setup();
    await store.createTag(scrum(1000));
    const id = store.getSnapshot().order[0];
    api.externalEdit(id, { end_ms: 7777 });
    await store.updateTag(id, { end_ms: 9000 });
    const state = store.getSnapshot();
    expect(state.notice).toContain('changed by someone else');
    expect(state.tags.get(id)).toMatchObject({ end_ms: 7777, version: 2 });
    expect(api.tags.get(id)?.end_ms).toBe(7777); // not overwritten
    // The failed command is not on the stack: undo reverts the create, not the update.
    await store.undo();
    expect(api.tags.has(id)).toBe(false);
    expect(store.getSnapshot().notice).toBeNull();
  });

  it('runs commands in order even when fired without awaiting', async () => {
    const { api, store } = await setup();
    void store.createTag(scrum(1000));
    void store.createTag(scrum(2000));
    await store.createTag(scrum(3000));
    const ids = store.getSnapshot().order;
    expect(ids).toHaveLength(3);
    void store.updateTag(ids[0], { note: 'a' });
    await store.updateTag(ids[0], { note: 'b' });
    expect(api.tags.get(ids[0])).toMatchObject({ note: 'b', version: 3 });
    await store.undo();
    await store.undo();
    expect(api.tags.get(ids[0])).toMatchObject({ note: null });
  });

  it('opens and closes spans', async () => {
    const { api, store } = await setup();
    await store.openSpan('Scrum', { code: 'Scrum', start_ms: 5000, end_ms: 6000 });
    expect(store.isOpen('Scrum')).toBe(true);
    const id = store.getSnapshot().openSpans.get('Scrum')!.tagId;
    await store.closeSpan('Scrum', 12_000);
    expect(store.isOpen('Scrum')).toBe(false);
    expect(api.tags.get(id)).toMatchObject({ start_ms: 5000, end_ms: 12_000 });
    await store.undo(); // reopens the end value, not the span state
    expect(api.tags.get(id)?.end_ms).toBe(6000);
    await store.undo(); // removes the tag
    expect(api.tags.has(id)).toBe(false);
  });

  it('keeps the selection and target tag consistent', async () => {
    const { store } = await setup();
    await store.createTag(scrum(1000));
    await store.createTag(scrum(2000));
    const [a, b] = store.getSnapshot().order;
    expect(store.targetTagId()).toBe(b);
    store.select([a]);
    expect(store.targetTagId()).toBe(a);
    store.toggleSelect(b);
    expect(store.getSnapshot().selected.size).toBe(2);
    expect(store.targetTagId()).toBe(b); // last touched, since two are selected
    store.clearSelection();
    expect(store.targetTagId()).toBe(b);
    await store.deleteTags([b]);
    expect(store.targetTagId()).toBeNull();
  });

  it('handles 1,500 tags without trouble', async () => {
    const { api, store } = await setup();
    for (let i = 0; i < 1500; i++) api.tags.set(`x${i}`, { ...(await api.create('e1', scrum(i * 3000))) });
    await store.load();
    expect(store.getSnapshot().order).toHaveLength(1500);
    const started = performance.now();
    store.select(['t1']);
    await store.updateTag('t1', { note: 'quick' });
    expect(performance.now() - started).toBeLessThan(200);
  });
});
