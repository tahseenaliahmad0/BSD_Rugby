"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-13 08:10:01.251204

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('model_versions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('task', sa.String(length=100), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('file_path', sa.String(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_versions')),
    sa.UniqueConstraint('name', 'version', name='uq_model_versions_name_version')
    )
    op.create_table('squads',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('sport_variant', sa.Enum('fifteens', 'sevens', name='sport_variant'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_squads')),
    sa.UniqueConstraint('name', name=op.f('uq_squads_name'))
    )
    op.create_table('users',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superadmin', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('memberships',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Enum('admin', 'analyst', 'coach', 'player', name='membership_role'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_memberships_squad_id_squads'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_memberships_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_memberships')),
    sa.UniqueConstraint('user_id', 'squad_id', name='uq_memberships_user_squad')
    )
    op.create_index(op.f('ix_memberships_squad_id'), 'memberships', ['squad_id'], unique=False)
    op.create_index(op.f('ix_memberships_user_id'), 'memberships', ['user_id'], unique=False)
    op.create_table('opponents',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('primary_colour', sa.String(length=32), nullable=True),
    sa.Column('secondary_colour', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_opponents_squad_id_squads'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_opponents')),
    sa.UniqueConstraint('squad_id', 'name', name='uq_opponents_squad_name')
    )
    op.create_index(op.f('ix_opponents_squad_id'), 'opponents', ['squad_id'], unique=False)
    op.create_table('playlists',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_playlists_owner_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_playlists_squad_id_squads'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_playlists'))
    )
    op.create_index(op.f('ix_playlists_squad_id'), 'playlists', ['squad_id'], unique=False)
    op.create_table('seasons',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_seasons_squad_id_squads'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_seasons')),
    sa.UniqueConstraint('squad_id', 'name', name='uq_seasons_squad_name')
    )
    op.create_index(op.f('ix_seasons_squad_id'), 'seasons', ['squad_id'], unique=False)
    op.create_table('sessions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=128), nullable=False),
    sa.Column('user_agent', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_sessions_token_hash'))
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('tag_templates',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('buttons', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('descriptor_groups', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_tag_templates_squad_id_squads'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tag_templates')),
    sa.UniqueConstraint('squad_id', 'name', 'version', name='uq_tag_templates')
    )
    op.create_index(op.f('ix_tag_templates_squad_id'), 'tag_templates', ['squad_id'], unique=False)
    op.create_table('events',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('season_id', sa.UUID(), nullable=True),
    sa.Column('opponent_id', sa.UUID(), nullable=True),
    sa.Column('type', sa.Enum('match', 'training', name='event_type'), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('kickoff_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('venue', sa.String(length=200), nullable=True),
    sa.Column('competition', sa.String(length=200), nullable=True),
    sa.Column('is_home', sa.Boolean(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_events_created_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['opponent_id'], ['opponents.id'], name=op.f('fk_events_opponent_id_opponents'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], name=op.f('fk_events_season_id_seasons'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_events_squad_id_squads'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_events'))
    )
    op.create_index(op.f('ix_events_opponent_id'), 'events', ['opponent_id'], unique=False)
    op.create_index(op.f('ix_events_season_id'), 'events', ['season_id'], unique=False)
    op.create_index('ix_events_squad_date', 'events', ['squad_id', 'date'], unique=False)
    op.create_table('players',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('season_id', sa.UUID(), nullable=True),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('shirt_number', sa.Integer(), nullable=True),
    sa.Column('position', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], name=op.f('fk_players_season_id_seasons'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_players_squad_id_squads'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_players_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_players'))
    )
    op.create_index(op.f('ix_players_season_id'), 'players', ['season_id'], unique=False)
    op.create_index(op.f('ix_players_squad_id'), 'players', ['squad_id'], unique=False)
    op.create_table('playlist_shares',
    sa.Column('playlist_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['playlist_id'], ['playlists.id'], name=op.f('fk_playlist_shares_playlist_id_playlists'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_playlist_shares_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('playlist_id', 'user_id', name=op.f('pk_playlist_shares'))
    )
    op.create_table('import_batches',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('source_filename', sa.String(length=500), nullable=False),
    sa.Column('source_path', sa.String(length=1000), nullable=True),
    sa.Column('format', sa.Enum('sportscode_xml', 'csv', name='import_format'), nullable=False),
    sa.Column('code_mapping', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('alignment_offset_s', sa.Float(), nullable=False),
    sa.Column('report', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.Enum('dry_run', 'applied', 'reverted', name='import_status'), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_import_batches_created_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], name=op.f('fk_import_batches_event_id_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_import_batches_squad_id_squads'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_batches'))
    )
    op.create_index(op.f('ix_import_batches_event_id'), 'import_batches', ['event_id'], unique=False)
    op.create_index(op.f('ix_import_batches_squad_id'), 'import_batches', ['squad_id'], unique=False)
    op.create_table('live_sessions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('client_uuid', sa.UUID(), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=True),
    sa.Column('device_id', sa.String(length=200), nullable=False),
    sa.Column('wall_clock_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('clock_offset_ms', sa.Integer(), nullable=False),
    sa.Column('sync_state', sa.Enum('pending', 'synced', 'aligned', name='live_sync_state'), nullable=False),
    sa.Column('anchors', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_live_sessions_created_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], name=op.f('fk_live_sessions_event_id_events'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_live_sessions_squad_id_squads'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_live_sessions')),
    sa.UniqueConstraint('client_uuid', name=op.f('uq_live_sessions_client_uuid'))
    )
    op.create_index(op.f('ix_live_sessions_event_id'), 'live_sessions', ['event_id'], unique=False)
    op.create_index(op.f('ix_live_sessions_squad_id'), 'live_sessions', ['squad_id'], unique=False)
    op.create_table('videos',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('camera_label', sa.String(length=100), nullable=False),
    sa.Column('original_filename', sa.String(length=500), nullable=False),
    sa.Column('original_path', sa.String(length=1000), nullable=False),
    sa.Column('original_size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('proxy_path', sa.String(length=1000), nullable=True),
    sa.Column('poster_path', sa.String(length=1000), nullable=True),
    sa.Column('thumbnails_path', sa.String(length=1000), nullable=True),
    sa.Column('thumbnail_interval_s', sa.Integer(), nullable=True),
    sa.Column('thumbnail_count', sa.Integer(), nullable=True),
    sa.Column('fps_num', sa.Integer(), nullable=True),
    sa.Column('fps_den', sa.Integer(), nullable=True),
    sa.Column('duration_s', sa.Float(), nullable=True),
    sa.Column('frame_count', sa.Integer(), nullable=True),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('offset_s', sa.Float(), nullable=False),
    sa.Column('status', sa.Enum('uploading', 'queued', 'processing', 'ready', 'failed', name='video_status'), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('uploaded_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], name=op.f('fk_videos_event_id_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_videos_uploaded_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_videos'))
    )
    op.create_index(op.f('ix_videos_event_id'), 'videos', ['event_id'], unique=False)
    op.create_table('jobs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('queue', sa.String(length=20), nullable=False),
    sa.Column('status', sa.Enum('queued', 'running', 'succeeded', 'failed', 'cancelled', name='job_status'), nullable=False),
    sa.Column('progress', sa.Float(), nullable=False),
    sa.Column('message', sa.String(length=500), nullable=True),
    sa.Column('log', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('video_id', sa.UUID(), nullable=True),
    sa.Column('squad_id', sa.UUID(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('celery_task_id', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_jobs_created_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_jobs_squad_id_squads'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], name=op.f('fk_jobs_video_id_videos'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs'))
    )
    op.create_index(op.f('ix_jobs_squad_id'), 'jobs', ['squad_id'], unique=False)
    op.create_index('ix_jobs_status_created', 'jobs', ['status', 'created_at'], unique=False)
    op.create_index(op.f('ix_jobs_video_id'), 'jobs', ['video_id'], unique=False)
    op.create_table('tags',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('template_id', sa.UUID(), nullable=True),
    sa.Column('code', sa.String(length=100), nullable=False),
    sa.Column('start_s', sa.Float(), nullable=False),
    sa.Column('end_s', sa.Float(), nullable=False),
    sa.Column('descriptors', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('source', sa.Enum('manual', 'live', 'import', 'ai', name='tag_source'), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('import_batch_id', sa.UUID(), nullable=True),
    sa.Column('live_session_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_tags_created_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], name=op.f('fk_tags_event_id_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], name=op.f('fk_tags_import_batch_id_import_batches'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['live_session_id'], ['live_sessions.id'], name=op.f('fk_tags_live_session_id_live_sessions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['template_id'], ['tag_templates.id'], name=op.f('fk_tags_template_id_tag_templates'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tags'))
    )
    op.create_index(op.f('ix_tags_code'), 'tags', ['code'], unique=False)
    op.create_index('ix_tags_descriptors', 'tags', ['descriptors'], unique=False, postgresql_using='gin')
    op.create_index('ix_tags_event_start', 'tags', ['event_id', 'start_s'], unique=False)
    op.create_index(op.f('ix_tags_import_batch_id'), 'tags', ['import_batch_id'], unique=False)
    op.create_table('uploads',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('squad_id', sa.UUID(), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('camera_label', sa.String(length=100), nullable=False),
    sa.Column('filename', sa.String(length=500), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('offset_bytes', sa.BigInteger(), nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('part_path', sa.String(length=1000), nullable=False),
    sa.Column('status', sa.Enum('in_progress', 'completed', 'aborted', 'expired', name='upload_status'), nullable=False),
    sa.Column('video_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], name=op.f('fk_uploads_event_id_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_uploads_squad_id_squads'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_uploads_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], name=op.f('fk_uploads_video_id_videos'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_uploads'))
    )
    op.create_index(op.f('ix_uploads_event_id'), 'uploads', ['event_id'], unique=False)
    op.create_table('live_tags',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('live_session_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=100), nullable=False),
    sa.Column('pressed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('lead_s', sa.Float(), nullable=False),
    sa.Column('descriptors', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tag_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['live_session_id'], ['live_sessions.id'], name=op.f('fk_live_tags_live_session_id_live_sessions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name=op.f('fk_live_tags_tag_id_tags'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_live_tags'))
    )
    op.create_index(op.f('ix_live_tags_live_session_id'), 'live_tags', ['live_session_id'], unique=False)
    op.create_table('playlist_items',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('playlist_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('tag_id', sa.UUID(), nullable=True),
    sa.Column('event_id', sa.UUID(), nullable=True),
    sa.Column('start_s', sa.Float(), nullable=True),
    sa.Column('end_s', sa.Float(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(tag_id IS NOT NULL) OR (event_id IS NOT NULL AND start_s IS NOT NULL AND end_s IS NOT NULL)', name=op.f('ck_playlist_items_tag_or_range')),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], name=op.f('fk_playlist_items_event_id_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['playlist_id'], ['playlists.id'], name=op.f('fk_playlist_items_playlist_id_playlists'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name=op.f('fk_playlist_items_tag_id_tags'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_playlist_items'))
    )
    op.create_index(op.f('ix_playlist_items_playlist_id'), 'playlist_items', ['playlist_id'], unique=False)
    op.create_table('suggestions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('video_id', sa.UUID(), nullable=False),
    sa.Column('model_version_id', sa.UUID(), nullable=True),
    sa.Column('code', sa.String(length=100), nullable=False),
    sa.Column('start_s', sa.Float(), nullable=False),
    sa.Column('end_s', sa.Float(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'accepted', 'rejected', 'adjusted', name='suggestion_status'), nullable=False),
    sa.Column('tag_id', sa.UUID(), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('reviewed_by', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], name=op.f('fk_suggestions_model_version_id_model_versions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], name=op.f('fk_suggestions_reviewed_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name=op.f('fk_suggestions_tag_id_tags'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], name=op.f('fk_suggestions_video_id_videos'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_suggestions'))
    )
    op.create_index('ix_suggestions_video_status', 'suggestions', ['video_id', 'status'], unique=False)
    op.create_table('tag_players',
    sa.Column('tag_id', sa.UUID(), nullable=False),
    sa.Column('player_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], name=op.f('fk_tag_players_player_id_players'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name=op.f('fk_tag_players_tag_id_tags'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tag_id', 'player_id', name=op.f('pk_tag_players'))
    )
    op.create_table('drawings',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('playlist_item_id', sa.UUID(), nullable=True),
    sa.Column('tag_id', sa.UUID(), nullable=True),
    sa.Column('timestamp_s', sa.Float(), nullable=False),
    sa.Column('shapes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(playlist_item_id IS NOT NULL) OR (tag_id IS NOT NULL)', name=op.f('ck_drawings_item_or_tag')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_drawings_created_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['playlist_item_id'], ['playlist_items.id'], name=op.f('fk_drawings_playlist_item_id_playlist_items'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name=op.f('fk_drawings_tag_id_tags'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_drawings'))
    )
    op.create_index(op.f('ix_drawings_playlist_item_id'), 'drawings', ['playlist_item_id'], unique=False)
    op.create_index(op.f('ix_drawings_tag_id'), 'drawings', ['tag_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_drawings_tag_id'), table_name='drawings')
    op.drop_index(op.f('ix_drawings_playlist_item_id'), table_name='drawings')
    op.drop_table('drawings')
    op.drop_table('tag_players')
    op.drop_index('ix_suggestions_video_status', table_name='suggestions')
    op.drop_table('suggestions')
    op.drop_index(op.f('ix_playlist_items_playlist_id'), table_name='playlist_items')
    op.drop_table('playlist_items')
    op.drop_index(op.f('ix_live_tags_live_session_id'), table_name='live_tags')
    op.drop_table('live_tags')
    op.drop_index(op.f('ix_uploads_event_id'), table_name='uploads')
    op.drop_table('uploads')
    op.drop_index(op.f('ix_tags_import_batch_id'), table_name='tags')
    op.drop_index('ix_tags_event_start', table_name='tags')
    op.drop_index('ix_tags_descriptors', table_name='tags', postgresql_using='gin')
    op.drop_index(op.f('ix_tags_code'), table_name='tags')
    op.drop_table('tags')
    op.drop_index(op.f('ix_jobs_video_id'), table_name='jobs')
    op.drop_index('ix_jobs_status_created', table_name='jobs')
    op.drop_index(op.f('ix_jobs_squad_id'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_index(op.f('ix_videos_event_id'), table_name='videos')
    op.drop_table('videos')
    op.drop_index(op.f('ix_live_sessions_squad_id'), table_name='live_sessions')
    op.drop_index(op.f('ix_live_sessions_event_id'), table_name='live_sessions')
    op.drop_table('live_sessions')
    op.drop_index(op.f('ix_import_batches_squad_id'), table_name='import_batches')
    op.drop_index(op.f('ix_import_batches_event_id'), table_name='import_batches')
    op.drop_table('import_batches')
    op.drop_table('playlist_shares')
    op.drop_index(op.f('ix_players_squad_id'), table_name='players')
    op.drop_index(op.f('ix_players_season_id'), table_name='players')
    op.drop_table('players')
    op.drop_index('ix_events_squad_date', table_name='events')
    op.drop_index(op.f('ix_events_season_id'), table_name='events')
    op.drop_index(op.f('ix_events_opponent_id'), table_name='events')
    op.drop_table('events')
    op.drop_index(op.f('ix_tag_templates_squad_id'), table_name='tag_templates')
    op.drop_table('tag_templates')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_index(op.f('ix_seasons_squad_id'), table_name='seasons')
    op.drop_table('seasons')
    op.drop_index(op.f('ix_playlists_squad_id'), table_name='playlists')
    op.drop_table('playlists')
    op.drop_index(op.f('ix_opponents_squad_id'), table_name='opponents')
    op.drop_table('opponents')
    op.drop_index(op.f('ix_memberships_user_id'), table_name='memberships')
    op.drop_index(op.f('ix_memberships_squad_id'), table_name='memberships')
    op.drop_table('memberships')
    op.drop_table('users')
    op.drop_table('squads')
    op.drop_table('model_versions')
    for enum_name in (
        'event_type',
        'import_format',
        'import_status',
        'job_status',
        'live_sync_state',
        'membership_role',
        'sport_variant',
        'suggestion_status',
        'tag_source',
        'upload_status',
        'video_status',
    ):
        op.execute(f'DROP TYPE IF EXISTS {enum_name}')
