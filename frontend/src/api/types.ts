export type Role = 'admin' | 'analyst' | 'coach' | 'player';
export type SportVariant = 'fifteens' | 'sevens';
export type EventType = 'match' | 'training';
export type VideoStatus = 'uploading' | 'queued' | 'processing' | 'ready' | 'failed';
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type UploadStatus = 'in_progress' | 'completed' | 'aborted' | 'expired';

export interface MembershipSummary {
  squad_id: string;
  squad_name: string;
  role: Role;
}

export interface Me {
  id: string;
  name: string;
  email: string;
  is_active: boolean;
  is_superadmin: boolean;
  created_at: string;
  memberships: MembershipSummary[];
  csrf_token: string;
}

export interface Squad {
  id: string;
  name: string;
  sport_variant: SportVariant;
  created_at: string;
  my_role: Role | null;
}

export interface Season {
  id: string;
  squad_id: string;
  name: string;
  start_date: string | null;
  end_date: string | null;
}

export interface Opponent {
  id: string;
  squad_id: string;
  name: string;
  primary_colour: string | null;
  secondary_colour: string | null;
}

export interface Video {
  id: string;
  event_id: string;
  camera_label: string;
  original_filename: string;
  original_size_bytes: number;
  status: VideoStatus;
  error: string | null;
  fps_num: number | null;
  fps_den: number | null;
  fps: number | null;
  duration_s: number | null;
  frame_count: number | null;
  width: number | null;
  height: number | null;
  offset_ms: number;
  thumbnail_interval_s: number | null;
  thumbnail_count: number | null;
  proxy_url: string | null;
  poster_url: string | null;
  thumbnail_url_template: string | null;
  original_url: string;
  created_at: string;
  updated_at: string;
}

export interface Event {
  id: string;
  squad_id: string;
  season_id: string | null;
  opponent_id: string | null;
  opponent_name: string | null;
  type: EventType;
  title: string | null;
  display_title: string;
  date: string;
  kickoff_at: string | null;
  venue: string | null;
  competition: string | null;
  is_home: boolean | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  video_count: number;
  videos: Video[];
}

export interface EventCreate {
  type: EventType;
  date: string;
  title?: string | null;
  season_id?: string | null;
  opponent_id?: string | null;
  opponent_name?: string | null;
  kickoff_at?: string | null;
  venue?: string | null;
  competition?: string | null;
  is_home?: boolean | null;
  notes?: string | null;
}

export interface Job {
  id: string;
  type: string;
  queue: string;
  status: JobStatus;
  progress: number;
  message: string | null;
  error: string | null;
  log: string | null;
  video_id: string | null;
  squad_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  output: Record<string, unknown>;
}

export interface UploadInfo {
  id: string;
  event_id: string;
  filename: string;
  size_bytes: number;
  offset_bytes: number;
  status: UploadStatus;
  video_id: string | null;
  created_at: string;
  expires_at: string;
}

// ---- Milestone 2 -----------------------------------------------------------------------

export interface Player {
  id: string;
  squad_id: string;
  season_id: string | null;
  name: string;
  shirt_number: number | null;
  position: string | null;
}

export interface Member {
  user_id: string;
  name: string;
  email: string;
  role: Role;
  is_active: boolean;
}

export interface DescriptorOption {
  value: string;
  label?: string | null;
  hotkey?: string | null;
}

export interface DescriptorGroup {
  key: string;
  label: string;
  kind: 'options' | 'players';
  multiple: boolean;
  options: DescriptorOption[];
}

export type ButtonKind = 'instant' | 'span';

export interface TemplateButton {
  code: string;
  label?: string | null;
  hotkey?: string | null;
  colour: string;
  kind: ButtonKind;
  lead_ms: number;
  lag_ms: number;
  groups: string[];
}

export interface TemplateContent {
  name: string;
  buttons: TemplateButton[];
  descriptor_groups: DescriptorGroup[];
  outcome_group: string | null;
  success_values: string[];
}

export interface Template extends TemplateContent {
  id: string;
  squad_id: string;
  family_id: string;
  version: number;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
}

export interface TemplateSummary {
  id: string;
  family_id: string;
  name: string;
  version: number;
  is_active: boolean;
  button_count: number;
  created_at: string;
}

export interface TemplateValidation {
  ok: boolean;
  errors: string[];
  clashes: string[];
}

export type Descriptors = Record<string, string | string[]>;
export type TagSource = 'manual' | 'live' | 'import' | 'ai';

export interface Tag {
  id: string;
  event_id: string;
  template_id: string | null;
  code: string;
  start_ms: number;
  end_ms: number;
  descriptors: Descriptors;
  player_ids: string[];
  note: string | null;
  source: TagSource;
  version: number;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface TagCreate {
  id?: string;
  template_id?: string | null;
  code: string;
  start_ms: number;
  end_ms: number;
  descriptors?: Descriptors;
  player_ids?: string[];
  note?: string | null;
}

export interface TagUpdate {
  version: number;
  code?: string;
  start_ms?: number;
  end_ms?: number;
  descriptors?: Descriptors;
  player_ids?: string[];
  note?: string | null;
}

export interface TagConflict {
  detail: string;
  current: Tag | null;
}

export interface FilterDefinition {
  codes?: string[];
  descriptors?: Record<string, string[]>;
  player_ids?: string[];
  event_ids?: string[];
  season_ids?: string[];
  opponent_ids?: string[];
  event_types?: EventType[];
  sources?: TagSource[];
  date_from?: string | null;
  date_to?: string | null;
  text?: string | null;
}

export interface ClipEvent {
  id: string;
  display_title: string;
  date: string;
  opponent_name: string | null;
  type: EventType;
}

export interface ClipVideo {
  id: string;
  proxy_url: string | null;
  poster_url: string | null;
  offset_ms: number;
  fps_num: number | null;
  fps_den: number | null;
  duration_s: number | null;
  thumbnail_url_template: string | null;
  thumbnail_interval_s: number | null;
  thumbnail_count: number | null;
}

export interface Clip {
  tag: Tag | null;
  event: ClipEvent;
  video: ClipVideo | null;
  code: string;
  label: string;
  start_ms: number;
  end_ms: number;
  start_s: number | null;
  end_s: number | null;
  thumbnail_url: string | null;
}

export interface SearchResult {
  total: number;
  clips: Clip[];
}

export interface SavedFilter {
  id: string;
  squad_id: string;
  owner_id: string | null;
  owner_name: string | null;
  name: string;
  definition: FilterDefinition;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
}

export interface RangeIn {
  event_id: string;
  video_id?: string | null;
  start_ms: number;
  end_ms: number;
  note?: string | null;
}

export interface PlaylistItem {
  id: string;
  position: number;
  note: string | null;
  tag_id: string | null;
  event_id: string;
  clip: Clip;
}

export interface Playlist {
  id: string;
  squad_id: string;
  owner_id: string | null;
  owner_name: string | null;
  name: string;
  description: string | null;
  filter_definition: FilterDefinition | null;
  saved_filter_id: string | null;
  item_count: number;
  can_edit: boolean;
  shared_with: { user_id: string; name: string }[];
  created_at: string;
  updated_at: string;
  items: PlaylistItem[];
}

export interface PlaylistCreate {
  name: string;
  description?: string | null;
  filter?: FilterDefinition | null;
  saved_filter_id?: string | null;
  tag_ids?: string[];
  ranges?: RangeIn[];
}

export interface CodeStat {
  code: string;
  label: string;
  colour: string | null;
  count: number;
  with_outcome: number;
  successes: number;
  success_rate: number | null;
  filter: FilterDefinition;
  success_filter: FilterDefinition | null;
  failure_filter: FilterDefinition | null;
}

export interface PlayerStat {
  player_id: string;
  name: string;
  shirt_number: number | null;
  total: number;
  by_code: Record<string, number>;
  with_outcome: number;
  successes: number;
  success_rate: number | null;
  filter: FilterDefinition;
}

export interface Stats {
  event_id: string | null;
  season_id: string | null;
  template_name: string | null;
  outcome_group: string | null;
  success_values: string[];
  tag_count: number;
  codes: CodeStat[];
  code_order: string[];
  players: PlayerStat[];
}

export interface ExportCreate {
  kind: 'clip' | 'playlist' | 'range';
  name?: string | null;
  tag_id?: string | null;
  playlist_id?: string | null;
  range?: RangeIn | null;
  with_captions?: boolean;
}

export interface Export {
  id: string;
  squad_id: string;
  owner_id: string | null;
  owner_name: string | null;
  name: string;
  kind: string;
  status: JobStatus;
  progress: number;
  with_captions: boolean;
  clip_count: number;
  file_url: string | null;
  size_bytes: number | null;
  error: string | null;
  job_id: string | null;
  created_at: string;
  finished_at: string | null;
}
