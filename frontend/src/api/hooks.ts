import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, queryString } from './client';
import type { Event, EventCreate, Job, Me, Opponent, Season, Squad, Video } from './types';

export const keys = {
  me: ['me'] as const,
  squads: ['squads'] as const,
  seasons: (squadId: string) => ['squads', squadId, 'seasons'] as const,
  opponents: (squadId: string) => ['squads', squadId, 'opponents'] as const,
  events: (squadId: string, filters: Record<string, string | undefined>) =>
    ['squads', squadId, 'events', filters] as const,
  event: (eventId: string) => ['events', eventId] as const,
  video: (videoId: string) => ['videos', videoId] as const,
  videoJobs: (videoId: string) => ['videos', videoId, 'jobs'] as const,
};

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return await api<Me>('/api/auth/me');
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api<Me>('/api/auth/login', { method: 'POST', body }),
    onSuccess: (me) => client.setQueryData(keys.me, me),
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ detail: string }>('/api/auth/logout', { method: 'POST' }),
    onSuccess: () => {
      client.setQueryData(keys.me, null);
      client.clear();
    },
  });
}

export function useSquads() {
  return useQuery({ queryKey: keys.squads, queryFn: () => api<Squad[]>('/api/squads') });
}

export function useSeasons(squadId: string) {
  return useQuery({
    queryKey: keys.seasons(squadId),
    queryFn: () => api<Season[]>(`/api/squads/${squadId}/seasons`),
  });
}

export function useOpponents(squadId: string) {
  return useQuery({
    queryKey: keys.opponents(squadId),
    queryFn: () => api<Opponent[]>(`/api/squads/${squadId}/opponents`),
  });
}

export type EventFilters = {
  season_id?: string;
  type?: string;
  q?: string;
};

export function useEvents(squadId: string, filters: EventFilters) {
  return useQuery({
    queryKey: keys.events(squadId, filters),
    queryFn: () => api<Event[]>(`/api/squads/${squadId}/events${queryString(filters)}`),
  });
}

export function useCreateEvent(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: EventCreate) =>
      api<Event>(`/api/squads/${squadId}/events`, { method: 'POST', body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['squads', squadId] });
    },
  });
}

export function useCreateSeason(squadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string }) =>
      api<Season>(`/api/squads/${squadId}/seasons`, { method: 'POST', body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.seasons(squadId) });
    },
  });
}

const VIDEO_BUSY = new Set(['uploading', 'queued', 'processing']);

export function useEvent(eventId: string) {
  return useQuery({
    queryKey: keys.event(eventId),
    queryFn: () => api<Event>(`/api/events/${eventId}`),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && data.videos.some((v) => VIDEO_BUSY.has(v.status)) ? 2000 : false;
    },
  });
}

export function useVideo(videoId: string | null) {
  return useQuery({
    queryKey: keys.video(videoId ?? ''),
    queryFn: () => api<Video>(`/api/videos/${videoId}`),
    enabled: videoId !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && VIDEO_BUSY.has(data.status) ? 1500 : false;
    },
  });
}

export function useVideoJobs(videoId: string | null, active: boolean) {
  return useQuery({
    queryKey: keys.videoJobs(videoId ?? ''),
    queryFn: () => api<Job[]>(`/api/videos/${videoId}/jobs`),
    enabled: videoId !== null,
    refetchInterval: active ? 1500 : false,
  });
}

export function useDeleteVideo(eventId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (videoId: string) => api<void>(`/api/videos/${videoId}`, { method: 'DELETE' }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.event(eventId) });
    },
  });
}
