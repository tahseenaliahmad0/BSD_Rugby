"""milestone 2 tagging

Times on the event timeline become integer milliseconds (ADR 0006), templates get a family
id and stats fields, tags get a version for optimistic concurrency (ADR 0007), and saved
filters and exports arrive. Every step is reversible; existing float seconds are converted.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_STATUS = postgresql.ENUM(
    'queued', 'running', 'succeeded', 'failed', 'cancelled', name='job_status', create_type=False
)


def _seconds_to_ms(table: str, old: str, new: str, *, nullable: bool, default: str | None) -> None:
    op.alter_column(
        table,
        old,
        new_column_name=new,
        type_=sa.Integer(),
        existing_type=sa.Float(),
        existing_nullable=nullable,
        postgresql_using=f'round({old} * 1000)::integer',
        server_default=default,
    )


def _ms_to_seconds(table: str, old: str, new: str, *, nullable: bool, default: str | None) -> None:
    op.alter_column(
        table,
        old,
        new_column_name=new,
        type_=sa.Float(),
        existing_type=sa.Integer(),
        existing_nullable=nullable,
        postgresql_using=f'{old} / 1000.0',
        server_default=default,
    )


def upgrade() -> None:
    # Milliseconds everywhere on the event timeline.
    _seconds_to_ms('videos', 'offset_s', 'offset_ms', nullable=False, default='0')
    _seconds_to_ms('tags', 'start_s', 'start_ms', nullable=False, default=None)
    _seconds_to_ms('tags', 'end_s', 'end_ms', nullable=False, default=None)
    _seconds_to_ms('suggestions', 'start_s', 'start_ms', nullable=False, default=None)
    _seconds_to_ms('suggestions', 'end_s', 'end_ms', nullable=False, default=None)
    _seconds_to_ms('playlist_items', 'start_s', 'start_ms', nullable=True, default=None)
    _seconds_to_ms('playlist_items', 'end_s', 'end_ms', nullable=True, default=None)
    _seconds_to_ms('drawings', 'timestamp_s', 'timestamp_ms', nullable=False, default=None)
    _seconds_to_ms('live_tags', 'lead_s', 'lead_ms', nullable=False, default='0')
    _seconds_to_ms(
        'import_batches', 'alignment_offset_s', 'alignment_offset_ms', nullable=False, default='0'
    )
    op.drop_constraint('tag_or_range', 'playlist_items', type_='check')
    op.create_check_constraint(
        'tag_or_range',
        'playlist_items',
        '(tag_id IS NOT NULL) OR (event_id IS NOT NULL AND start_ms IS NOT NULL '
        'AND end_ms IS NOT NULL)',
    )

    # Tags: concurrency version, editor, extra index.
    op.add_column(
        'tags', sa.Column('version', sa.Integer(), nullable=False, server_default='1')
    )
    op.add_column('tags', sa.Column('updated_by', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_tags_updated_by_users'), 'tags', 'users', ['updated_by'], ['id'],
        ondelete='SET NULL',
    )
    op.drop_index(op.f('ix_tags_event_start'), table_name='tags')
    op.create_index('ix_tags_event_start', 'tags', ['event_id', 'start_ms'], unique=False)
    op.create_index('ix_tags_event_code', 'tags', ['event_id', 'code'], unique=False)

    # Templates: families of versions, stats definition, author.
    op.add_column(
        'tag_templates',
        sa.Column('family_id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
    )
    op.alter_column('tag_templates', 'family_id', server_default=None)
    op.add_column('tag_templates', sa.Column('outcome_group', sa.String(length=50), nullable=True))
    op.add_column(
        'tag_templates',
        sa.Column(
            'success_values', postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column('tag_templates', sa.Column('created_by', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_tag_templates_created_by_users'), 'tag_templates', 'users', ['created_by'],
        ['id'], ondelete='SET NULL',
    )
    op.drop_constraint('uq_tag_templates', 'tag_templates', type_='unique')
    op.create_index(op.f('ix_tag_templates_family_id'), 'tag_templates', ['family_id'], unique=False)
    op.create_unique_constraint(
        'uq_tag_templates_family_version', 'tag_templates', ['family_id', 'version']
    )

    # Saved filters.
    op.create_table(
        'saved_filters',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('squad_id', sa.UUID(), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_shared', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_saved_filters_owner_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_saved_filters_squad_id_squads'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_saved_filters')),
    )
    op.create_index(op.f('ix_saved_filters_owner_id'), 'saved_filters', ['owner_id'], unique=False)
    op.create_index(op.f('ix_saved_filters_squad_id'), 'saved_filters', ['squad_id'], unique=False)

    # Playlists: filter source and pinned video on ad-hoc ranges.
    op.add_column('playlists', sa.Column('filter_definition', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('playlists', sa.Column('saved_filter_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_playlists_saved_filter_id_saved_filters'), 'playlists', 'saved_filters',
        ['saved_filter_id'], ['id'], ondelete='SET NULL',
    )
    op.add_column('playlist_items', sa.Column('video_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_playlist_items_video_id_videos'), 'playlist_items', 'videos', ['video_id'],
        ['id'], ondelete='SET NULL',
    )

    # Exports.
    op.create_table(
        'exports',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('squad_id', sa.UUID(), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('playlist_id', sa.UUID(), nullable=True),
        sa.Column('clips', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('with_captions', sa.Boolean(), nullable=False),
        sa.Column('status', JOB_STATUS, nullable=False),
        sa.Column('progress', sa.Float(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=True),
        sa.Column('file_path', sa.String(length=1000), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name=op.f('fk_exports_job_id_jobs'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_exports_owner_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['playlist_id'], ['playlists.id'], name=op.f('fk_exports_playlist_id_playlists'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_exports_squad_id_squads'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_exports')),
    )
    op.create_index(op.f('ix_exports_squad_id'), 'exports', ['squad_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_exports_squad_id'), table_name='exports')
    op.drop_table('exports')

    op.drop_constraint(op.f('fk_playlist_items_video_id_videos'), 'playlist_items', type_='foreignkey')
    op.drop_column('playlist_items', 'video_id')
    op.drop_constraint(op.f('fk_playlists_saved_filter_id_saved_filters'), 'playlists', type_='foreignkey')
    op.drop_column('playlists', 'saved_filter_id')
    op.drop_column('playlists', 'filter_definition')

    op.drop_index(op.f('ix_saved_filters_squad_id'), table_name='saved_filters')
    op.drop_index(op.f('ix_saved_filters_owner_id'), table_name='saved_filters')
    op.drop_table('saved_filters')

    op.drop_constraint('uq_tag_templates_family_version', 'tag_templates', type_='unique')
    op.drop_index(op.f('ix_tag_templates_family_id'), table_name='tag_templates')
    op.create_unique_constraint('uq_tag_templates', 'tag_templates', ['squad_id', 'name', 'version'])
    op.drop_constraint(op.f('fk_tag_templates_created_by_users'), 'tag_templates', type_='foreignkey')
    op.drop_column('tag_templates', 'created_by')
    op.drop_column('tag_templates', 'success_values')
    op.drop_column('tag_templates', 'outcome_group')
    op.drop_column('tag_templates', 'family_id')

    op.drop_index('ix_tags_event_code', table_name='tags')
    op.drop_index('ix_tags_event_start', table_name='tags')
    op.drop_constraint(op.f('fk_tags_updated_by_users'), 'tags', type_='foreignkey')
    op.drop_column('tags', 'updated_by')
    op.drop_column('tags', 'version')

    op.drop_constraint('tag_or_range', 'playlist_items', type_='check')
    _ms_to_seconds('import_batches', 'alignment_offset_ms', 'alignment_offset_s', nullable=False, default='0')
    _ms_to_seconds('live_tags', 'lead_ms', 'lead_s', nullable=False, default='0')
    _ms_to_seconds('drawings', 'timestamp_ms', 'timestamp_s', nullable=False, default=None)
    _ms_to_seconds('playlist_items', 'end_ms', 'end_s', nullable=True, default=None)
    _ms_to_seconds('playlist_items', 'start_ms', 'start_s', nullable=True, default=None)
    _ms_to_seconds('suggestions', 'end_ms', 'end_s', nullable=False, default=None)
    _ms_to_seconds('suggestions', 'start_ms', 'start_s', nullable=False, default=None)
    _ms_to_seconds('tags', 'end_ms', 'end_s', nullable=False, default=None)
    _ms_to_seconds('tags', 'start_ms', 'start_s', nullable=False, default=None)
    _ms_to_seconds('videos', 'offset_ms', 'offset_s', nullable=False, default='0')
    op.create_check_constraint(
        'tag_or_range',
        'playlist_items',
        '(tag_id IS NOT NULL) OR (event_id IS NOT NULL AND start_s IS NOT NULL '
        'AND end_s IS NOT NULL)',
    )
    op.create_index(op.f('ix_tags_event_start'), 'tags', ['event_id', 'start_s'], unique=False)
