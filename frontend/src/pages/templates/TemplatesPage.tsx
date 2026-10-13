import { Badge, Button, Group, Loader, Paper, Stack, Text, Title } from '@mantine/core';
import { IconPlus, IconSparkles } from '@tabler/icons-react';
import { Link, Navigate, useNavigate, useParams } from 'react-router';
import { useCreateDefaultTemplates, useCreateTemplate, useTemplates } from '../../api/hooksM2';
import { useAuth } from '../../auth/AuthContext';

export function TemplatesPage() {
  const { squadId = '' } = useParams();
  const { canEdit } = useAuth();
  const navigate = useNavigate();
  const { data: templates, isPending } = useTemplates(squadId);
  const defaults = useCreateDefaultTemplates(squadId);
  const create = useCreateTemplate(squadId);

  if (!canEdit(squadId)) return <Navigate to={`/squads/${squadId}`} replace />;

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <div>
          <Title order={1}>Tag templates</Title>
          <Text c="dimmed">The buttons and hotkeys of the code window. Editing makes a new version; old tags keep theirs.</Text>
        </div>
        <Group>
          {templates && templates.length === 0 && (
            <Button variant="light" leftSection={<IconSparkles size={18} />} loading={defaults.isPending} onClick={() => defaults.mutate()}>
              Add the rugby defaults
            </Button>
          )}
          <Button
            leftSection={<IconPlus size={18} />}
            loading={create.isPending}
            onClick={() =>
              create.mutate(
                { name: 'New template', buttons: [], descriptor_groups: [], outcome_group: null, success_values: [] },
                { onSuccess: (t) => navigate(`/templates/${t.id}`) },
              )
            }
            data-testid="new-template"
          >
            New template
          </Button>
        </Group>
      </Group>
      {isPending && <Loader />}
      <Stack gap="sm">
        {templates?.map((t) => (
          <Paper key={t.id} withBorder p="md" radius="md" component={Link} to={`/templates/${t.id}`} className="event-card" data-testid="template-card">
            <Group justify="space-between" wrap="wrap">
              <div>
                <Text fw={700} size="lg">{t.name}</Text>
                <Text c="dimmed">
                  {t.buttons.length} buttons · {t.descriptor_groups.length} descriptor groups · version {t.version}
                </Text>
              </div>
              <Group gap="xs">
                {t.buttons.slice(0, 8).map((b) => (
                  <Badge key={b.code} variant="filled" style={{ backgroundColor: b.colour }}>
                    {b.label || b.code}
                  </Badge>
                ))}
                {t.buttons.length > 8 && <Badge variant="light">+{t.buttons.length - 8}</Badge>}
              </Group>
            </Group>
          </Paper>
        ))}
      </Stack>
    </Stack>
  );
}
