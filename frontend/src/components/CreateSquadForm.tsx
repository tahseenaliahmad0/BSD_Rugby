import { Alert, Button, SegmentedControl, Stack, Text, TextInput } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { ApiError } from '../api/client';
import { useCreateSquad } from '../api/hooks';
import type { SportVariant } from '../api/types';
import { rememberSquad } from './squadMemory';

/**
 * Creates a squad (administrators only) and opens it. The server adds the creator as the
 * squad's admin and installs the default tagging templates for the chosen form of the game.
 */
export function CreateSquadForm({ onDone }: { onDone?: () => void }) {
  const [name, setName] = useState('');
  const [variant, setVariant] = useState<SportVariant>('fifteens');
  const create = useCreateSquad();
  const navigate = useNavigate();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    create.mutate(
      { name: trimmed, sport_variant: variant },
      {
        onSuccess: (squad) => {
          rememberSquad(squad.id);
          onDone?.();
          navigate(`/squads/${squad.id}`);
        },
      },
    );
  };
  const error =
    create.error instanceof ApiError ? create.error.detail : create.error ? create.error.message : null;

  return (
    <form onSubmit={submit}>
      <Stack gap="sm">
        <TextInput
          label="Squad name"
          placeholder="Men's 1st XV"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          required
          maxLength={200}
          data-autofocus
          data-testid="new-squad-name"
        />
        <div>
          <Text size="sm" fw={500} mb={4}>
            Form of the game
          </Text>
          <SegmentedControl
            value={variant}
            onChange={(v) => setVariant(v as SportVariant)}
            data={[
              { value: 'fifteens', label: '15s' },
              { value: 'sevens', label: 'Sevens' },
            ]}
            data-testid="new-squad-variant"
          />
          <Text size="xs" c="dimmed" mt={4}>
            Picks the default tagging template. You can change templates later.
          </Text>
        </div>
        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}
        <Button type="submit" loading={create.isPending} data-testid="new-squad-submit">
          Create squad
        </Button>
      </Stack>
    </form>
  );
}
