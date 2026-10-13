/**
 * One playlist: continuous playback across clips from different matches, with next/previous,
 * drag-to-reorder, notes, sharing, duplicating, refreshing from its search and MP4 export.
 */
import { closestCenter, DndContext, KeyboardSensor, PointerSensor, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  Loader,
  Menu,
  Modal,
  MultiSelect,
  Paper,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconArrowLeft,
  IconChevronLeft,
  IconChevronRight,
  IconCopy,
  IconDotsVertical,
  IconDownload,
  IconGripVertical,
  IconPencil,
  IconPlayerPlay,
  IconRefresh,
  IconShare,
  IconTrash,
} from '@tabler/icons-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import {
  useCreateExport,
  useDeletePlaylist,
  useDeletePlaylistItem,
  useDuplicatePlaylist,
  useMembers,
  usePlaylist,
  useRefreshPlaylist,
  useReorderPlaylist,
  useSetPlaylistShares,
  useUpdatePlaylist,
  useUpdatePlaylistItem,
} from '../api/hooksM2';
import type { PlaylistItem } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { clipDurationS, clipTitle } from '../clips/clipLabel';
import { ClipPlayer } from '../clips/ClipPlayer';
import { formatDate } from '../components/format';
import type { PlayerHandle } from '../player/VideoPlayer';

function isTyping(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
}

function SortableClip({ item, index, active, canEdit, onPick, onNote, onRemove }: { item: PlaylistItem; index: number; active: boolean; canEdit: boolean; onPick: () => void; onNote: (note: string | null) => void; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id, disabled: !canEdit });
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState(item.note ?? '');
  const [noteSource, setNoteSource] = useState(item.note);
  if (item.note !== noteSource) {
    setNoteSource(item.note);
    setNote(item.note ?? '');
  }
  return (
    <Paper ref={setNodeRef} withBorder p="xs" radius="sm" style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1, borderColor: active ? 'var(--mantine-primary-color-filled)' : undefined }} data-testid="playlist-item">
      <Group gap="xs" wrap="nowrap" align="flex-start">
        {canEdit && (
          <ActionIcon variant="subtle" color="gray" {...attributes} {...listeners} aria-label="Drag to reorder" style={{ cursor: 'grab', touchAction: 'none' }}>
            <IconGripVertical size={18} />
          </ActionIcon>
        )}
        <div style={{ flex: 1, minWidth: 0, cursor: 'pointer' }} onClick={onPick} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onPick()}>
          <Group gap="xs" wrap="nowrap" align="flex-start">
            {item.clip.thumbnail_url ? <img src={item.clip.thumbnail_url} alt="" style={{ width: 96, aspectRatio: '16/9', objectFit: 'cover', borderRadius: 4, background: '#111' }} loading="lazy" /> : <div style={{ width: 96, aspectRatio: '16/9', background: '#333', borderRadius: 4 }} />}
            <div style={{ minWidth: 0 }}>
              <Text fw={active ? 700 : 600} size="sm" lineClamp={2}>
                {index + 1}. {clipTitle(item.clip)}
              </Text>
              <Text size="xs" c="dimmed" lineClamp={1}>
                {item.clip.event.display_title} · {formatDate(item.clip.event.date)} · {clipDurationS(item.clip).toFixed(0)} s
              </Text>
              {!editing && item.note && (
                <Text size="xs" fs="italic" lineClamp={2}>{item.note}</Text>
              )}
            </div>
          </Group>
          {editing && (
            <Textarea size="xs" mt={4} autosize minRows={1} value={note} onChange={(e) => setNote(e.currentTarget.value)} onClick={(e) => e.stopPropagation()} onBlur={() => { setEditing(false); onNote(note.trim() || null); }} autoFocus data-testid="item-note" />
          )}
        </div>
        {canEdit && (
          <Menu position="bottom-end" shadow="md">
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray" aria-label="Clip options">
                <IconDotsVertical size={18} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconPencil size={16} />} onClick={() => setEditing(true)}>Add or edit note</Menu.Item>
              <Menu.Item leftSection={<IconTrash size={16} />} color="red" onClick={onRemove}>Remove from playlist</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        )}
      </Group>
    </Paper>
  );
}

export function PlaylistPage() {
  const { playlistId = '' } = useParams();
  const navigate = useNavigate();
  const { me } = useAuth();
  const { data: playlist, isPending, error } = usePlaylist(playlistId);
  const squadId = playlist?.squad_id;
  const update = useUpdatePlaylist(squadId);
  const remove = useDeletePlaylist(squadId);
  const reorder = useReorderPlaylist(squadId);
  const updateItem = useUpdatePlaylistItem(squadId);
  const deleteItem = useDeletePlaylistItem(squadId);
  const refresh = useRefreshPlaylist(squadId);
  const duplicate = useDuplicatePlaylist(squadId);
  const setShares = useSetPlaylistShares(squadId);
  const createExport = useCreateExport(squadId ?? '');
  const { data: members } = useMembers(squadId ?? '', !!playlist?.can_edit);

  const [index, setIndex] = useState(0);
  const [autoPlay, setAutoPlay] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState('');
  const [shareOpen, setShareOpen] = useState(false);
  const [shareWith, setShareWith] = useState<string[]>([]);
  const [exportOpen, setExportOpen] = useState(false);
  const [captions, setCaptions] = useState(true);
  const [order, setOrder] = useState<string[] | null>(null);
  const playerRef = useRef<PlayerHandle>(null);

  // A fresh playlist from the server replaces any local order from a drag in progress.
  const [orderFor, setOrderFor] = useState(playlist);
  if (playlist !== orderFor) {
    setOrderFor(playlist);
    setOrder(null);
  }
  const items = playlist ? (order ? order.map((id) => playlist.items.find((i) => i.id === id)).filter((i): i is PlaylistItem => !!i) : playlist.items) : [];
  const current = items[index] ?? null;

  const goTo = (next: number, play = true) => {
    if (next < 0 || next >= items.length) return;
    setIndex(next);
    setAutoPlay(play);
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === 'n' || event.key === 'N' || event.key === 'PageDown') {
        event.preventDefault();
        goTo(index + 1);
      } else if (event.key === 'p' || event.key === 'P' || event.key === 'PageUp') {
        event.preventDefault();
        goTo(index - 1);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, items.length]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));
  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!playlist || !over || active.id === over.id) return;
    const ids = items.map((i) => i.id);
    const next = arrayMove(ids, ids.indexOf(String(active.id)), ids.indexOf(String(over.id)));
    setOrder(next);
    const currentId = current?.id;
    if (currentId) setIndex(next.indexOf(currentId));
    reorder.mutate({ playlistId: playlist.id, item_ids: next });
  };

  if (isPending) return <Loader />;
  if (error || !playlist) return <Alert color="red">Could not open this playlist. {error?.message}</Alert>;
  const canEdit = playlist.can_edit;

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <div style={{ minWidth: 0 }}>
          <Button component={Link} to={`/squads/${playlist.squad_id}/playlists`} variant="subtle" leftSection={<IconArrowLeft size={18} />} px={0}>
            All playlists
          </Button>
          {renaming ? (
            <Group gap="xs">
              <TextInput value={name} onChange={(e) => setName(e.currentTarget.value)} autoFocus data-testid="rename-input" onKeyDown={(e) => { if (e.key === 'Enter') { update.mutate({ playlistId: playlist.id, body: { name: name.trim() || playlist.name } }); setRenaming(false); } if (e.key === 'Escape') setRenaming(false); }} />
              <Button size="sm" onClick={() => { update.mutate({ playlistId: playlist.id, body: { name: name.trim() || playlist.name } }); setRenaming(false); }}>Save</Button>
            </Group>
          ) : (
            <Group gap="xs" align="center">
              <Title order={1} data-testid="playlist-title">{playlist.name}</Title>
              {canEdit && (
                <Tooltip label="Rename">
                  <ActionIcon variant="subtle" aria-label="Rename" onClick={() => { setName(playlist.name); setRenaming(true); }} data-testid="rename">
                    <IconPencil size={18} />
                  </ActionIcon>
                </Tooltip>
              )}
            </Group>
          )}
          <Text c="dimmed" size="sm">
            {items.length} clip{items.length === 1 ? '' : 's'} · {playlist.owner_id === me.id ? 'yours' : `by ${playlist.owner_name}`}
            {playlist.shared_with.length > 0 ? ` · shared with ${playlist.shared_with.map((s) => s.name).join(', ')}` : ''}
          </Text>
        </div>
        <Group gap="xs" wrap="wrap">
          <Button leftSection={<IconPlayerPlay size={18} />} onClick={() => goTo(0)} disabled={items.length === 0} data-testid="play-all">
            Play all
          </Button>
          <Button variant="light" leftSection={<IconDownload size={18} />} onClick={() => setExportOpen(true)} disabled={items.length === 0} data-testid="export-playlist">
            Export MP4
          </Button>
          {canEdit && (
            <Button variant="light" leftSection={<IconShare size={18} />} onClick={() => { setShareWith(playlist.shared_with.map((s) => s.user_id)); setShareOpen(true); }} data-testid="share-playlist">
              Share
            </Button>
          )}
          <Menu position="bottom-end" shadow="md">
            <Menu.Target>
              <ActionIcon size="lg" variant="light" aria-label="More">
                <IconDotsVertical size={20} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconCopy size={16} />} onClick={() => duplicate.mutate(playlist.id, { onSuccess: (p) => navigate(`/playlists/${p.id}`) })}>Duplicate</Menu.Item>
              {canEdit && playlist.filter_definition && (
                <Menu.Item leftSection={<IconRefresh size={16} />} onClick={() => refresh.mutate(playlist.id, { onSuccess: (p) => notifications.show({ color: 'green', message: `Refreshed: ${p.item_count} clips now match.` }) })} data-testid="refresh-playlist">
                  Refresh from the search
                </Menu.Item>
              )}
              {canEdit && (
                <Menu.Item leftSection={<IconTrash size={16} />} color="red" onClick={() => { if (window.confirm(`Delete "${playlist.name}"?`)) remove.mutate(playlist.id, { onSuccess: () => navigate(`/squads/${playlist.squad_id}/playlists`) }); }}>
                  Delete playlist
                </Menu.Item>
              )}
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>

      <div className="tagging-grid">
        <div>
          {current ? (
            <Stack gap="xs">
              <ClipPlayer key={current.id} ref={playerRef} clip={current.clip} autoPlay={autoPlay} note={current.note} onEnded={() => { if (index + 1 < items.length) goTo(index + 1); }} />
              <Group justify="space-between">
                <Button variant="light" leftSection={<IconChevronLeft size={18} />} disabled={index === 0} onClick={() => goTo(index - 1)} data-testid="prev-clip">
                  Previous (P)
                </Button>
                <Text c="dimmed" data-testid="clip-position">Clip {index + 1} of {items.length}</Text>
                <Button variant="light" rightSection={<IconChevronRight size={18} />} disabled={index >= items.length - 1} onClick={() => goTo(index + 1)} data-testid="next-clip">
                  Next (N)
                </Button>
              </Group>
            </Stack>
          ) : (
            <Paper withBorder p="xl" radius="md">
              <Text c="dimmed" ta="center">This playlist is empty. Find clips and add them here.</Text>
            </Paper>
          )}
        </div>
        <Paper withBorder p="sm" radius="md" style={{ maxHeight: 640, overflowY: 'auto' }}>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
              <Stack gap="xs">
                {items.map((item, i) => (
                  <SortableClip key={item.id} item={item} index={i} active={i === index} canEdit={canEdit} onPick={() => goTo(i)} onNote={(note) => updateItem.mutate({ playlistId: playlist.id, itemId: item.id, body: { note } })} onRemove={() => { deleteItem.mutate({ playlistId: playlist.id, itemId: item.id }); if (i < index) setIndex(index - 1); }} />
                ))}
              </Stack>
            </SortableContext>
          </DndContext>
        </Paper>
      </div>

      <Modal opened={shareOpen} onClose={() => setShareOpen(false)} title="Share this playlist">
        <Stack>
          <MultiSelect label="Share with" placeholder="Pick staff in the squad" data={(members ?? []).filter((m) => m.user_id !== me.id).map((m) => ({ value: m.user_id, label: `${m.name} (${m.role})` }))} value={shareWith} onChange={setShareWith} searchable data-testid="share-picker" />
          <Button loading={setShares.isPending} onClick={() => setShares.mutate({ playlistId: playlist.id, user_ids: shareWith }, { onSuccess: () => { setShareOpen(false); notifications.show({ color: 'green', message: 'Sharing updated.' }); } })} data-testid="share-confirm">
            Save
          </Button>
        </Stack>
      </Modal>

      <Modal opened={exportOpen} onClose={() => setExportOpen(false)} title="Export as MP4">
        <Stack>
          <Text size="sm">All {items.length} clips are joined into one video. It is made in the background; find it under Downloads.</Text>
          <Checkbox label="Show the code and note on each clip" checked={captions} onChange={(e) => setCaptions(e.currentTarget.checked)} />
          <Button loading={createExport.isPending} onClick={() => createExport.mutate({ kind: 'playlist', playlist_id: playlist.id, with_captions: captions }, { onSuccess: () => { setExportOpen(false); notifications.show({ color: 'green', message: 'Export started. It will appear under Downloads.' }); navigate(`/squads/${playlist.squad_id}/downloads`); } })} data-testid="export-confirm">
            Start export
          </Button>
          <Badge variant="light" color="gray">Original quality where the original file is still on the server</Badge>
        </Stack>
      </Modal>
    </Stack>
  );
}
