import { api } from '../api/client';
import type { Tag, TagCreate, TagUpdate } from '../api/types';
import type { TagApi } from './store';

/** The real API behind the tag store. */
export const httpTagApi: TagApi = {
  list: (eventId) => api<Tag[]>(`/api/events/${eventId}/tags`),
  create: (eventId, body: TagCreate) => api<Tag>(`/api/events/${eventId}/tags`, { method: 'POST', body }),
  update: (tagId, body: TagUpdate) => api<Tag>(`/api/tags/${tagId}`, { method: 'PATCH', body }),
  remove: (tagId, version) => api<void>(`/api/tags/${tagId}?version=${version}`, { method: 'DELETE' }),
  batch: (eventId, body) => api(`/api/events/${eventId}/tags/batch`, { method: 'POST', body }),
  split: (tagId, version, atMs) => api(`/api/tags/${tagId}/split`, { method: 'POST', body: { version, at_ms: atMs } }),
  merge: (eventId, refs) => api<Tag>(`/api/events/${eventId}/tags/merge`, { method: 'POST', body: { tags: refs } }),
};
