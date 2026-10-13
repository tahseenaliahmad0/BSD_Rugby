import { Center, Paper, Stack, Text, Title } from '@mantine/core';
import { Navigate } from 'react-router';
import { useSquads } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';
import { CreateSquadForm } from '../components/CreateSquadForm';
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
      <Stack align="center" w="100%" maw={420}>
        <Title order={2}>No squads yet</Title>
        {me.is_superadmin ? (
          <>
            <Text c="dimmed" ta="center">
              Create the first squad. You can add more later from the menu under your name.
            </Text>
            <Paper withBorder p="md" w="100%">
              <CreateSquadForm />
            </Paper>
          </>
        ) : (
          <Text c="dimmed" ta="center">
            Ask your analyst or administrator to add you to a squad.
          </Text>
        )}
      </Stack>
    </Center>
  );
}
