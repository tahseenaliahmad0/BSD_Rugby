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
