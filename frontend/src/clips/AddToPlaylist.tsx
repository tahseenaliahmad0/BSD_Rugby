import { Button, Menu, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconPlaylistAdd } from '@tabler/icons-react';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAddPlaylistItems, useCreatePlaylist, usePlaylists } from '../api/hooksM2';
import type { FilterDefinition } from '../api/types';

interface Props {
  squadId: string;
  /** Tags to add (hand-picked) ... */
  tagIds?: string[];
  /** ... or a filter to snapshot into a new playlist. */
  filter?: FilterDefinition;
  label?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  variant?: string;
}

/** "Add to playlist": pick an existing playlist you can edit, or make a new one. */
export function AddToPlaylist({ squadId, tagIds = [], filter, label = 'Add to playlist', size = 'sm', variant = 'light' }: Props) {
  const navigate = useNavigate();
  const { data: playlists } = usePlaylists(squadId);
  const add = useAddPlaylistItems(squadId);
  const create = useCreatePlaylist(squadId);
  const [name, setName] = useState('');
  const editable = (playlists ?? []).filter((p) => p.can_edit);

  const createNew = () => {
    const playlistName = name.trim() || (filter ? 'New playlist' : 'My clips');
    create.mutate(
      { name: playlistName, filter: filter ?? null, tag_ids: filter ? [] : tagIds },
      {
        onSuccess: (playlist) => {
          notifications.show({ color: 'green', message: `Made "${playlist.name}" with ${playlist.item_count} clip${playlist.item_count === 1 ? '' : 's'}.` });
          navigate(`/playlists/${playlist.id}`);
        },
      },
    );
  };

  return (
    <Menu shadow="md" width={280} position="bottom-start" closeOnItemClick={false}>
      <Menu.Target>
        <Button size={size} variant={variant} leftSection={<IconPlaylistAdd size={18} />} data-testid="add-to-playlist">
          {label}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {!filter && editable.length > 0 && (
          <>
            <Menu.Label>Add to an existing playlist</Menu.Label>
            {editable.slice(0, 8).map((p) => (
              <Menu.Item
                key={p.id}
                closeMenuOnClick
                onClick={() =>
                  add.mutate(
                    { playlistId: p.id, tag_ids: tagIds },
                    { onSuccess: () => notifications.show({ color: 'green', message: `Added to "${p.name}".` }) },
                  )
                }
              >
                {p.name} ({p.item_count})
              </Menu.Item>
            ))}
            <Menu.Divider />
          </>
        )}
        <Menu.Label>{filter ? 'Save these clips as a new playlist' : 'Or make a new playlist'}</Menu.Label>
        <div style={{ padding: '4px 10px 8px' }}>
          <TextInput size="sm" placeholder="Playlist name" value={name} onChange={(e) => setName(e.currentTarget.value)} onKeyDown={(e) => e.key === 'Enter' && createNew()} data-testid="new-playlist-name" />
          <Button size="sm" mt="xs" fullWidth loading={create.isPending} onClick={createNew} data-testid="new-playlist-create">
            Create playlist
          </Button>
        </div>
      </Menu.Dropdown>
    </Menu>
  );
}
