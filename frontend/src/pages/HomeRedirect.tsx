import { Center, Stack, Text, Title } from '@mantine/core';
import { Navigate } from 'react-router';
import { useSquads } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';
import { lastSquad } from '../components/squadMemory';

/** Send the user to the squad they used last, or their first squad. */
export function HomeRedirect() {
  const { me } = useAuth();
  const { data: squads, isPending } = useSquads();
  if (isPending) return null;
  const ids = (squads ?? []).map((s) => s.id);
  const remembered = lastSquad();
  const target = remembered && ids.includes(remembered) ? remembered : ids[0];
  if (target) return <Navigate to={`/squads/${target}`} replace />;
  return (
    <Center mt="xl">
      <Stack align="center">
        <Title order={2}>No squads yet</Title>
        <Text c="dimmed" ta="center" maw={480}>
          {me.is_superadmin
            ? 'Create a squad from the API or the seed script, then come back here.'
            : 'Ask your analyst or administrator to add you to a squad.'}
        </Text>
      </Stack>
    </Center>
  );
}
