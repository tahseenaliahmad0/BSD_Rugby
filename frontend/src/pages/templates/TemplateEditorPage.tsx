import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  ColorInput,
  Group,
  Kbd,
  Loader,
  MultiSelect,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconAlertCircle,
  IconArrowDown,
  IconArrowLeft,
  IconArrowUp,
  IconCheck,
  IconDeviceFloppy,
  IconPlus,
  IconTrash,
} from '@tabler/icons-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { ApiError } from '../../api/client';
import {
  useActivateTemplateVersion,
  useSaveTemplateVersion,
  useTemplate,
  useTemplateVersions,
  validateTemplate,
} from '../../api/hooksM2';
import type { DescriptorGroup, Template, TemplateButton, TemplateContent, TemplateSummary, TemplateValidation } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { COLOURS, keyLabel, localClashes, PLAYER_KEYS } from './templateClashes';

function move<T>(list: T[], from: number, to: number): T[] {
  if (to < 0 || to >= list.length) return list;
  const next = [...list];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export function TemplateEditorPage() {
  const { templateId = '' } = useParams();
  const { canEdit } = useAuth();
  const { data: template, isPending } = useTemplate(templateId);
  const { data: versions } = useTemplateVersions(templateId);

  if (isPending) return <Loader />;
  if (!template) return <Alert color="red">Template not found.</Alert>;
  if (!canEdit(template.squad_id)) return <Alert color="red">Only analysts and admins can edit templates.</Alert>;
  return <TemplateEditor key={template.id} template={template} versions={versions ?? []} />;
}

function TemplateEditor({ template, versions }: { template: Template; versions: TemplateSummary[] }) {
  const navigate = useNavigate();
  const save = useSaveTemplateVersion(template.squad_id);
  const activate = useActivateTemplateVersion(template.squad_id);

  const [draft, setDraft] = useState<TemplateContent>(() => ({
    name: template.name,
    buttons: template.buttons,
    descriptor_groups: template.descriptor_groups,
    outcome_group: template.outcome_group,
    success_values: template.success_values,
  }));
  const [serverCheck, setServerCheck] = useState<TemplateValidation | null>(null);
  const [debouncedDraft] = useDebouncedValue(draft, 400);

  useEffect(() => {
    let cancelled = false;
    validateTemplate(template.squad_id, debouncedDraft)
      .then((result) => {
        if (!cancelled) setServerCheck(result);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [debouncedDraft, template]);

  const problems = useMemo(() => localClashes(draft), [draft]);
  const dirty = useMemo(
    () =>
      JSON.stringify(draft) !==
      JSON.stringify({
        name: template.name,
        buttons: template.buttons,
        descriptor_groups: template.descriptor_groups,
        outcome_group: template.outcome_group,
        success_values: template.success_values,
      }),
    [draft, template],
  );

  const groupOptions = draft.descriptor_groups.map((g) => ({ value: g.key, label: g.label }));
  const outcomeGroup = draft.descriptor_groups.find((g) => g.key === draft.outcome_group);
  const allErrors = [...problems, ...(serverCheck?.errors.filter((e) => !problems.includes(e)) ?? [])];

  const updateButton = (index: number, patch: Partial<TemplateButton>) =>
    setDraft({ ...draft, buttons: draft.buttons.map((b, i) => (i === index ? { ...b, ...patch } : b)) });
  const updateGroup = (index: number, patch: Partial<DescriptorGroup>) =>
    setDraft({ ...draft, descriptor_groups: draft.descriptor_groups.map((g, i) => (i === index ? { ...g, ...patch } : g)) });

  const doSave = () => {
    save.mutate(
      { templateId: template.id, body: draft },
      {
        onSuccess: (saved) => {
          notifications.show({ color: 'green', message: `Saved as version ${saved.version}.`, icon: <IconCheck size={16} /> });
          navigate(`/templates/${saved.id}`, { replace: true });
        },
        onError: (error) => {
          notifications.show({ color: 'red', message: error instanceof ApiError ? error.detail : error.message });
        },
      },
    );
  };

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <div>
          <Button component={Link} to={`/squads/${template.squad_id}/templates`} variant="subtle" leftSection={<IconArrowLeft size={18} />} px={0}>
            All templates
          </Button>
          <Group gap="sm" align="center">
            <Title order={1}>{template.name}</Title>
            <Badge variant={template.is_active ? 'filled' : 'light'} color={template.is_active ? 'green' : 'gray'}>
              version {template.version}{template.is_active ? ' (in use)' : ''}
            </Badge>
          </Group>
        </div>
        <Group>
          {!template.is_active && (
            <Button variant="light" onClick={() => activate.mutate(template.id)} loading={activate.isPending}>
              Use this version
            </Button>
          )}
          <Button
            leftSection={<IconDeviceFloppy size={18} />}
            onClick={doSave}
            loading={save.isPending}
            disabled={!dirty || problems.length > 0}
            data-testid="template-save"
          >
            Save as new version
          </Button>
        </Group>
      </Group>

      {allErrors.length > 0 && (
        <Alert color="red" icon={<IconAlertCircle size={18} />} data-testid="template-problems">
          <Stack gap={2}>
            {allErrors.map((p) => (
              <Text key={p} size="sm">{p}</Text>
            ))}
          </Stack>
        </Alert>
      )}

      <Paper withBorder p="lg" radius="md">
        <Stack gap="md">
          <TextInput label="Template name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.currentTarget.value })} maw={420} />
          <Group align="flex-end">
            <Select
              label="Outcome group (for success rates)"
              data={groupOptions.filter((g) => draft.descriptor_groups.find((d) => d.key === g.value)?.kind === 'options')}
              value={draft.outcome_group}
              onChange={(v) => setDraft({ ...draft, outcome_group: v, success_values: v === draft.outcome_group ? draft.success_values : [] })}
              clearable
              maw={320}
            />
            <MultiSelect
              label="Values that count as success"
              data={(outcomeGroup?.options ?? []).map((o) => ({ value: o.value, label: o.label || o.value }))}
              value={draft.success_values}
              onChange={(v) => setDraft({ ...draft, success_values: v })}
              disabled={!outcomeGroup}
              maw={420}
            />
          </Group>
        </Stack>
      </Paper>

      <Paper withBorder p="lg" radius="md">
        <Group justify="space-between" mb="sm">
          <div>
            <Title order={3}>Buttons</Title>
            <Text c="dimmed" size="sm">
              Hotkeys are single letters or digits. The player keeps Space, J, K, L, F, M, comma and full stop. Use Shift+letter for descriptor options.
            </Text>
          </div>
          <Button
            variant="light"
            leftSection={<IconPlus size={18} />}
            onClick={() =>
              setDraft({
                ...draft,
                buttons: [...draft.buttons, { code: `Code ${draft.buttons.length + 1}`, label: null, hotkey: null, colour: COLOURS[draft.buttons.length % COLOURS.length], kind: 'instant', lead_ms: 3000, lag_ms: 3000, groups: [] }],
              })
            }
            data-testid="add-button"
          >
            Add button
          </Button>
        </Group>
        <Table verticalSpacing="xs" withRowBorders={false} layout="fixed">
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={80}>Order</Table.Th>
              <Table.Th>Code</Table.Th>
              <Table.Th w={110}>Hotkey</Table.Th>
              <Table.Th w={150}>Colour</Table.Th>
              <Table.Th w={190}>Type</Table.Th>
              <Table.Th w={100}>Lead (s)</Table.Th>
              <Table.Th w={100}>Lag (s)</Table.Th>
              <Table.Th>Descriptor groups</Table.Th>
              <Table.Th w={50} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {draft.buttons.map((b, i) => (
              <Table.Tr key={i} data-testid="button-row">
                <Table.Td>
                  <Group gap={2} wrap="nowrap">
                    <ActionIcon variant="subtle" aria-label="Move up" onClick={() => setDraft({ ...draft, buttons: move(draft.buttons, i, i - 1) })} disabled={i === 0}>
                      <IconArrowUp size={16} />
                    </ActionIcon>
                    <ActionIcon variant="subtle" aria-label="Move down" onClick={() => setDraft({ ...draft, buttons: move(draft.buttons, i, i + 1) })} disabled={i === draft.buttons.length - 1}>
                      <IconArrowDown size={16} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <TextInput size="sm" value={b.code} onChange={(e) => updateButton(i, { code: e.currentTarget.value })} aria-label="Code" />
                </Table.Td>
                <Table.Td>
                  <TextInput
                    size="sm"
                    value={b.hotkey ?? ''}
                    maxLength={1}
                    placeholder="key"
                    aria-label="Hotkey"
                    onKeyDown={(e) => {
                      if (e.key.length === 1) {
                        e.preventDefault();
                        updateButton(i, { hotkey: e.key });
                      } else if (e.key === 'Backspace' || e.key === 'Delete') {
                        updateButton(i, { hotkey: null });
                      }
                    }}
                    onChange={() => undefined}
                    error={b.hotkey ? (PLAYER_KEYS.has(b.hotkey) ? 'Player key' : undefined) : undefined}
                  />
                </Table.Td>
                <Table.Td>
                  <ColorInput size="sm" value={b.colour} onChange={(v) => updateButton(i, { colour: v })} swatches={COLOURS} format="hex" aria-label="Colour" />
                </Table.Td>
                <Table.Td>
                  <SegmentedControl
                    size="xs"
                    value={b.kind}
                    onChange={(v) => updateButton(i, { kind: v as 'instant' | 'span' })}
                    data={[{ value: 'instant', label: 'Instant' }, { value: 'span', label: 'Start/stop' }]}
                  />
                </Table.Td>
                <Table.Td>
                  <NumberInput size="sm" value={b.lead_ms / 1000} min={0} max={120} step={0.5} disabled={b.kind === 'span'} onChange={(v) => updateButton(i, { lead_ms: Math.round(Number(v || 0) * 1000) })} aria-label="Lead seconds" />
                </Table.Td>
                <Table.Td>
                  <NumberInput size="sm" value={b.lag_ms / 1000} min={0} max={120} step={0.5} disabled={b.kind === 'span'} onChange={(v) => updateButton(i, { lag_ms: Math.round(Number(v || 0) * 1000) })} aria-label="Lag seconds" />
                </Table.Td>
                <Table.Td>
                  <MultiSelect size="sm" data={groupOptions} value={b.groups} onChange={(v) => updateButton(i, { groups: v })} aria-label="Descriptor groups" />
                </Table.Td>
                <Table.Td>
                  <Tooltip label="Remove button">
                    <ActionIcon variant="subtle" color="red" aria-label="Remove button" onClick={() => setDraft({ ...draft, buttons: draft.buttons.filter((_, j) => j !== i) })}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Tooltip>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>

      <Paper withBorder p="lg" radius="md">
        <Group justify="space-between" mb="sm">
          <div>
            <Title order={3}>Descriptor groups</Title>
            <Text c="dimmed" size="sm">Extra detail on a tag: outcome, zone, players and so on. A "players" group uses the roster.</Text>
          </div>
          <Button
            variant="light"
            leftSection={<IconPlus size={18} />}
            onClick={() =>
              setDraft({ ...draft, descriptor_groups: [...draft.descriptor_groups, { key: `group_${draft.descriptor_groups.length + 1}`, label: 'New group', kind: 'options', multiple: false, options: [] }] })
            }
          >
            Add group
          </Button>
        </Group>
        <Stack gap="md">
          {draft.descriptor_groups.map((g, i) => (
            <Paper key={i} withBorder p="md" radius="sm">
              <Group align="flex-end" wrap="wrap">
                <TextInput label="Label" size="sm" value={g.label} onChange={(e) => updateGroup(i, { label: e.currentTarget.value })} />
                <TextInput label="Key" size="sm" value={g.key} onChange={(e) => updateGroup(i, { key: e.currentTarget.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') })} description="letters, digits, underscores" />
                <SegmentedControl size="xs" value={g.kind} onChange={(v) => updateGroup(i, { kind: v as 'options' | 'players', options: v === 'players' ? [] : g.options })} data={[{ value: 'options', label: 'Options' }, { value: 'players', label: 'Players' }]} />
                <Checkbox label="Allow several values" checked={g.multiple} onChange={(e) => updateGroup(i, { multiple: e.currentTarget.checked })} />
                <ActionIcon variant="subtle" color="red" aria-label="Remove group" onClick={() => setDraft({ ...draft, descriptor_groups: draft.descriptor_groups.filter((_, j) => j !== i), buttons: draft.buttons.map((b) => ({ ...b, groups: b.groups.filter((k) => k !== g.key) })), outcome_group: draft.outcome_group === g.key ? null : draft.outcome_group, success_values: draft.outcome_group === g.key ? [] : draft.success_values })}>
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
              {g.kind === 'options' && (
                <Group mt="sm" gap="xs" wrap="wrap">
                  {g.options.map((o, j) => (
                    <Group key={j} gap={4} wrap="nowrap">
                      <TextInput size="xs" value={o.value} w={130} aria-label="Option" onChange={(e) => updateGroup(i, { options: g.options.map((x, k) => (k === j ? { ...x, value: e.currentTarget.value } : x)) })} />
                      <TextInput
                        size="xs"
                        w={70}
                        value={o.hotkey ?? ''}
                        placeholder="key"
                        aria-label="Option hotkey"
                        onKeyDown={(e) => {
                          if (e.key.length === 1) {
                            e.preventDefault();
                            updateGroup(i, { options: g.options.map((x, k) => (k === j ? { ...x, hotkey: e.key } : x)) });
                          } else if (e.key === 'Backspace' || e.key === 'Delete') {
                            updateGroup(i, { options: g.options.map((x, k) => (k === j ? { ...x, hotkey: null } : x)) });
                          }
                        }}
                        onChange={() => undefined}
                      />
                      {o.hotkey && <Kbd size="xs">{keyLabel(o.hotkey)}</Kbd>}
                      <ActionIcon size="sm" variant="subtle" color="red" aria-label="Remove option" onClick={() => updateGroup(i, { options: g.options.filter((_, k) => k !== j) })}>
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Group>
                  ))}
                  <Button size="xs" variant="light" leftSection={<IconPlus size={14} />} onClick={() => updateGroup(i, { options: [...g.options, { value: `Option ${g.options.length + 1}`, hotkey: null }] })}>
                    Add option
                  </Button>
                </Group>
              )}
            </Paper>
          ))}
        </Stack>
      </Paper>

      {versions.length > 1 && (
        <Paper withBorder p="lg" radius="md">
          <Title order={3} mb="sm">Versions</Title>
          <Table withRowBorders={false}>
            <Table.Tbody>
              {versions.map((v) => (
                <Table.Tr key={v.id}>
                  <Table.Td>
                    <Button component={Link} to={`/templates/${v.id}`} variant="subtle" size="compact-sm">
                      Version {v.version}
                    </Button>
                  </Table.Td>
                  <Table.Td>{v.button_count} buttons</Table.Td>
                  <Table.Td>{new Date(v.created_at).toLocaleString()}</Table.Td>
                  <Table.Td>{v.is_active && <Badge color="green">in use</Badge>}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
    </Stack>
  );
}
