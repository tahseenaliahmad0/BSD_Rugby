/** TanStack Query hooks for the Milestone 2 API: templates, tags, clips, playlists, stats, exports. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  Export,
  ExportCreate,
  FilterDefinition,
  Member,
  Player,
  Playlist,
  PlaylistCreate,
  PlaylistItem,
  RangeIn,
  SavedFilter,
  SearchResult,
  Stats,
  Tag,
  Template,
  TemplateContent,
  TemplateSummary,
  TemplateValidation,
} from './types';

export const m2keys = {
  templates: (squadId: string) => ['squads', squadId, 'templates'] as const,
  template: (id: string) => ['templates', id] as const,
  templateVersions: (id: string) => ['templates', id, 'versions'] as const,
  players: (squadId: string) => ['squads', squadId, 'players'] as const,
  members: (squadId: string) => ['squads', squadId, 'members'] as const,
  tags: (eventId: string) => ['events', eventId, 'tags'] as const,
  search: (squadId: string, filter: FilterDefinition, limit: number, offset: number) =>
    ['squads', squadId, 'clips', filter, limit, offset] as const,
  filters: (squadId: string) => ['squads', squadId, 'filters'] as const,
  playlists: (squadId: string) => ['squads', squadId, 'playlists'] as const,
  playlist: (id: string) => ['playlists', id] as const,
  stats: (squadId: string, params: Record<string, string | undefined>) =>
    ['squads', squadId, 'stats', params] as const,
  exports: (squadId: string) => ['squads', squadId, 'exports'] as const,
};

// Templates -----------------------------------------------------------------------------
export function useTemplates(squadId: string) {
  return useQuery({
    queryKey: m2keys.templates(squadId),
    queryFn: () => api<Template[]>(`/api/squads/${squadId}/templates`),
    enabled: !!squadId,
  });
}

export function useTemplate(templateId: string | null) {
  return useQuery({
    queryKey: m2keys.template(templateId ?? ''),
    queryFn: () => api<Template>(`/api/templates/${templateId}`),
    enabled: !!templateId,
  });
}

export function useTemplateVersions(templateId: string | null) {
  return useQuery({
    queryKey: m2keys.templateVersions(templateId ?? ''),
    queryFn: () => api<TemplateSummary[]>(`/api/templates/${templateId}/versions`),
    enabled: !!templateId,
  });
}

export function useCreateTemplate(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: TemplateContent) =>
      api<Template>(`/api/squads/${squadId}/templates`, { method: 'POST', body }),
    onSuccess: () => void client.invalidateQueries({ queryKey: m2keys.templates(squadId) }),
  });
}

export function useCreateDefaultTemplates(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<Template[]>(`/api/squads/${squadId}/templates/defaults`, { method: 'POST' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: m2keys.templates(squadId) }),
  });
}

export function useSaveTemplateVersion(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ templateId, body }: { templateId: string; body: TemplateContent }) =>
      api<Template>(`/api/templates/${templateId}`, { method: 'PUT', body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: m2keys.templates(squadId) });
      void client.invalidateQueries({ queryKey: ['templates'] });
    },
  });
}

export function useActivateTemplateVersion(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (templateId: string) =>
      api<Template>(`/api/templates/${templateId}/activate`, { method: 'POST' }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: m2keys.templates(squadId) });
      void client.invalidateQueries({ queryKey: ['templates'] });
    },
  });
}

export function validateTemplate(squadId: string, body: TemplateContent) {
  return api<TemplateValidation>(`/api/squads/${squadId}/templates/validate`, { method: 'POST', body });
}

// Roster and members ---------------------------------------------------------------------
export function usePlayers(squadId: string) {
  return useQuery({
    queryKey: m2keys.players(squadId),
    queryFn: () => api<Player[]>(`/api/squads/${squadId}/players`),
    enabled: !!squadId,
  });
}

export function useMembers(squadId: string, enabled = true) {
  return useQuery({
    queryKey: m2keys.members(squadId),
    queryFn: () => api<Member[]>(`/api/squads/${squadId}/members`),
    enabled: !!squadId && enabled,
  });
}

// Tags -----------------------------------------------------------------------------------
export function useEventTags(eventId: string) {
  return useQuery({
    queryKey: m2keys.tags(eventId),
    queryFn: () => api<Tag[]>(`/api/events/${eventId}/tags`),
    enabled: !!eventId,
    staleTime: 0,
  });
}

// Clips and saved filters ----------------------------------------------------------------
export function useSearchClips(squadId: string, filter: FilterDefinition, limit = 200, offset = 0, enabled = true) {
  return useQuery({
    queryKey: m2keys.search(squadId, filter, limit, offset),
    queryFn: () =>
      api<SearchResult>(`/api/squads/${squadId}/clips/search`, {
        method: 'POST',
        body: { filter, limit, offset },
      }),
    enabled: !!squadId && enabled,
    placeholderData: (previous) => previous,
  });
}

export function useSavedFilters(squadId: string) {
  return useQuery({
    queryKey: m2keys.filters(squadId),
    queryFn: () => api<SavedFilter[]>(`/api/squads/${squadId}/filters`),
    enabled: !!squadId,
  });
}

export function useCreateSavedFilter(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; definition: FilterDefinition; is_shared: boolean }) =>
      api<SavedFilter>(`/api/squads/${squadId}/filters`, { method: 'POST', body }),
    onSuccess: () => void client.invalidateQueries({ queryKey: m2keys.filters(squadId) }),
  });
}

export function useDeleteSavedFilter(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (filterId: string) => api<void>(`/api/filters/${filterId}`, { method: 'DELETE' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: m2keys.filters(squadId) }),
  });
}

// Playlists ------------------------------------------------------------------------------
export function usePlaylists(squadId: string) {
  return useQuery({
    queryKey: m2keys.playlists(squadId),
    queryFn: () => api<Playlist[]>(`/api/squads/${squadId}/playlists`),
    enabled: !!squadId,
  });
}

export function usePlaylist(playlistId: string) {
  return useQuery({
    queryKey: m2keys.playlist(playlistId),
    queryFn: () => api<Playlist>(`/api/playlists/${playlistId}`),
    enabled: !!playlistId,
  });
}

function usePlaylistMutation<TVars, TResult>(
  squadId: string | undefined,
  fn: (vars: TVars) => Promise<TResult>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['playlists'] });
      if (squadId) void client.invalidateQueries({ queryKey: m2keys.playlists(squadId) });
    },
  });
}

export function useCreatePlaylist(squadId: string) {
  return usePlaylistMutation(squadId, (body: PlaylistCreate) =>
    api<Playlist>(`/api/squads/${squadId}/playlists`, { method: 'POST', body }),
  );
}

export function useUpdatePlaylist(squadId?: string) {
  return usePlaylistMutation(squadId, ({ playlistId, body }: { playlistId: string; body: { name?: string; description?: string | null } }) =>
    api<Playlist>(`/api/playlists/${playlistId}`, { method: 'PATCH', body }),
  );
}

export function useDeletePlaylist(squadId?: string) {
  return usePlaylistMutation(squadId, (playlistId: string) =>
    api<void>(`/api/playlists/${playlistId}`, { method: 'DELETE' }),
  );
}

export function useAddPlaylistItems(squadId?: string) {
  return usePlaylistMutation(squadId, ({ playlistId, tag_ids, ranges }: { playlistId: string; tag_ids?: string[]; ranges?: RangeIn[] }) =>
    api<PlaylistItem[]>(`/api/playlists/${playlistId}/items`, { method: 'POST', body: { tag_ids: tag_ids ?? [], ranges: ranges ?? [] } }),
  );
}

export function useUpdatePlaylistItem(squadId?: string) {
  return usePlaylistMutation(squadId, ({ playlistId, itemId, body }: { playlistId: string; itemId: string; body: { note?: string | null; start_ms?: number; end_ms?: number } }) =>
    api<PlaylistItem>(`/api/playlists/${playlistId}/items/${itemId}`, { method: 'PATCH', body }),
  );
}

export function useDeletePlaylistItem(squadId?: string) {
  return usePlaylistMutation(squadId, ({ playlistId, itemId }: { playlistId: string; itemId: string }) =>
    api<void>(`/api/playlists/${playlistId}/items/${itemId}`, { method: 'DELETE' }),
  );
}

export function useReorderPlaylist(squadId?: string) {
  return usePlaylistMutation(squadId, ({ playlistId, item_ids }: { playlistId: string; item_ids: string[] }) =>
    api<Playlist>(`/api/playlists/${playlistId}/order`, { method: 'PUT', body: { item_ids } }),
  );
}

export function useRefreshPlaylist(squadId?: string) {
  return usePlaylistMutation(squadId, (playlistId: string) =>
    api<Playlist>(`/api/playlists/${playlistId}/refresh`, { method: 'POST' }),
  );
}

export function useDuplicatePlaylist(squadId?: string) {
  return usePlaylistMutation(squadId, (playlistId: string) =>
    api<Playlist>(`/api/playlists/${playlistId}/duplicate`, { method: 'POST' }),
  );
}

export function useSetPlaylistShares(squadId?: string) {
  return usePlaylistMutation(squadId, ({ playlistId, user_ids }: { playlistId: string; user_ids: string[] }) =>
    api<Playlist>(`/api/playlists/${playlistId}/shares`, { method: 'PUT', body: { user_ids } }),
  );
}

// Stats ----------------------------------------------------------------------------------
export function useStats(squadId: string, params: { event_id?: string; season_id?: string }) {
  const search = new URLSearchParams();
  if (params.event_id) search.set('event_id', params.event_id);
  if (params.season_id) search.set('season_id', params.season_id);
  const qs = search.toString();
  return useQuery({
    queryKey: m2keys.stats(squadId, params),
    queryFn: () => api<Stats>(`/api/squads/${squadId}/stats${qs ? `?${qs}` : ''}`),
    enabled: !!squadId,
  });
}

export function statsCsvUrl(squadId: string, table: 'codes' | 'players', params: { event_id?: string; season_id?: string }) {
  const search = new URLSearchParams({ format: 'csv', table });
  if (params.event_id) search.set('event_id', params.event_id);
  if (params.season_id) search.set('season_id', params.season_id);
  return `/api/squads/${squadId}/stats?${search.toString()}`;
}

// Exports --------------------------------------------------------------------------------
const EXPORT_BUSY = new Set(['queued', 'running']);

export function useExports(squadId: string) {
  return useQuery({
    queryKey: m2keys.exports(squadId),
    queryFn: () => api<Export[]>(`/api/squads/${squadId}/exports`),
    enabled: !!squadId,
    refetchInterval: (query) =>
      query.state.data?.some((e) => EXPORT_BUSY.has(e.status)) ? 2000 : false,
  });
}

export function useCreateExport(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ExportCreate) =>
      api<Export>(`/api/squads/${squadId}/exports`, { method: 'POST', body }),
    onSuccess: () => void client.invalidateQueries({ queryKey: m2keys.exports(squadId) }),
  });
}

export function useDeleteExport(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (exportId: string) => api<void>(`/api/exports/${exportId}`, { method: 'DELETE' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: m2keys.exports(squadId) }),
  });
}
