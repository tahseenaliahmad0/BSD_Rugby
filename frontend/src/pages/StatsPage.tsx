/** Stats per match or season. Every number opens the matching clips as a playlist. */
import { Button, Group, Loader, Paper, Select, Stack, Table, Text, Title, UnstyledButton } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconDownload } from '@tabler/icons-react';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { useEvents, useSeasons } from '../api/hooks';
import { statsCsvUrl, useCreatePlaylist, useStats } from '../api/hooksM2';
import type { FilterDefinition } from '../api/types';
import { formatDate } from '../components/format';

function pct(rate: number | null): string {
  return rate === null ? '–' : `${Math.round(rate * 100)}%`;
}

export function StatsPage() {
  const { squadId = '' } = useParams();
  const navigate = useNavigate();
  const { data: seasons } = useSeasons(squadId);
  const { data: events } = useEvents(squadId, {});
  const [seasonId, setSeasonId] = useState<string | null>(null);
  const [eventId, setEventId] = useState<string | null>(null);
  const params = { event_id: eventId ?? undefined, season_id: eventId ? undefined : (seasonId ?? undefined) };
  const { data: stats, isPending } = useStats(squadId, params);
  const create = useCreatePlaylist(squadId);

  const open = (name: string, filter: FilterDefinition | null) => {
    if (!filter) return;
    create.mutate(
      { name, filter },
      {
        onSuccess: (p) => {
          notifications.show({ color: 'green', message: `Opened ${p.item_count} clips as "${p.name}".` });
          navigate(`/playlists/${p.id}`);
        },
      },
    );
  };

  const scopeName = eventId ? (events?.find((e) => e.id === eventId)?.display_title ?? 'match') : seasonId ? (seasons?.find((s) => s.id === seasonId)?.name ?? 'season') : 'all matches';

  const Num = ({ value, name, filter }: { value: number | string; name: string; filter: FilterDefinition | null }) => (
    <UnstyledButton onClick={() => open(name, filter)} disabled={!filter} style={{ fontVariantNumeric: 'tabular-nums', textDecoration: filter ? 'underline dotted' : undefined, fontSize: 'inherit' }} title={filter ? 'Open these clips as a playlist' : undefined} data-testid="stat-number">
      {value}
    </UnstyledButton>
  );

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <div>
          <Title order={1}>Stats</Title>
          <Text c="dimmed">Counts and success rates from the tags. Click any number to watch those clips.</Text>
        </div>
        <Group>
          <Select label="Season" placeholder="All seasons" data={(seasons ?? []).map((s) => ({ value: s.id, label: s.name }))} value={seasonId} onChange={(v) => { setSeasonId(v); setEventId(null); }} clearable w={180} />
          <Select label="Match" placeholder="All matches" data={(events ?? []).map((e) => ({ value: e.id, label: `${e.display_title} · ${formatDate(e.date)}` }))} value={eventId} onChange={setEventId} clearable searchable w={300} data-testid="stats-match" />
        </Group>
      </Group>

      {isPending && <Loader />}
      {stats && (
        <>
          <Paper withBorder p="md" radius="md">
            <Group justify="space-between" mb="sm">
              <div>
                <Title order={3}>By code · {scopeName}</Title>
                <Text size="sm" c="dimmed">
                  {stats.tag_count} tags{stats.outcome_group ? ` · success means ${stats.outcome_group} = ${stats.success_values.join(' or ')}` : ' · no outcome group in the template, so no success rates'}
                </Text>
              </div>
              <Button component="a" href={statsCsvUrl(squadId, 'codes', params)} download variant="light" leftSection={<IconDownload size={16} />} size="sm">
                CSV
              </Button>
            </Group>
            <Table striped highlightOnHover data-testid="codes-table">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Code</Table.Th>
                  <Table.Th ta="right">Count</Table.Th>
                  <Table.Th ta="right">With outcome</Table.Th>
                  <Table.Th ta="right">Successes</Table.Th>
                  <Table.Th ta="right">Success rate</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {stats.codes.map((row) => (
                  <Table.Tr key={row.code}>
                    <Table.Td>
                      <Group gap={6}>
                        <span style={{ width: 10, height: 10, borderRadius: 2, background: row.colour ?? '#868e96', display: 'inline-block' }} />
                        {row.label}
                      </Group>
                    </Table.Td>
                    <Table.Td ta="right"><Num value={row.count} name={`${row.label} · ${scopeName}`} filter={row.filter} /></Table.Td>
                    <Table.Td ta="right">{row.with_outcome}</Table.Td>
                    <Table.Td ta="right"><Num value={row.successes} name={`${row.label} won · ${scopeName}`} filter={row.success_filter} /></Table.Td>
                    <Table.Td ta="right"><Num value={pct(row.success_rate)} name={`${row.label} lost · ${scopeName}`} filter={row.failure_filter} /></Table.Td>
                  </Table.Tr>
                ))}
                {stats.codes.length === 0 && (
                  <Table.Tr><Table.Td colSpan={5}><Text c="dimmed">No tags yet for this selection.</Text></Table.Td></Table.Tr>
                )}
              </Table.Tbody>
            </Table>
          </Paper>

          <Paper withBorder p="md" radius="md">
            <Group justify="space-between" mb="sm">
              <Title order={3}>By player · {scopeName}</Title>
              <Button component="a" href={statsCsvUrl(squadId, 'players', params)} download variant="light" leftSection={<IconDownload size={16} />} size="sm">
                CSV
              </Button>
            </Group>
            <div style={{ overflowX: 'auto' }}>
              <Table striped highlightOnHover data-testid="players-table">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Player</Table.Th>
                    <Table.Th ta="right">Total</Table.Th>
                    {stats.code_order.map((code) => (
                      <Table.Th key={code} ta="right">{stats.codes.find((c) => c.code === code)?.label ?? code}</Table.Th>
                    ))}
                    <Table.Th ta="right">Success rate</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {stats.players.map((row) => (
                    <Table.Tr key={row.player_id}>
                      <Table.Td>{row.shirt_number != null ? `${row.shirt_number} ` : ''}{row.name}</Table.Td>
                      <Table.Td ta="right"><Num value={row.total} name={`${row.name} · ${scopeName}`} filter={row.filter} /></Table.Td>
                      {stats.code_order.map((code) => (
                        <Table.Td key={code} ta="right">
                          <Num value={row.by_code[code] ?? 0} name={`${row.name} · ${code}`} filter={row.by_code[code] ? { ...row.filter, codes: [code] } : null} />
                        </Table.Td>
                      ))}
                      <Table.Td ta="right">{pct(row.success_rate)}</Table.Td>
                    </Table.Tr>
                  ))}
                  {stats.players.length === 0 && (
                    <Table.Tr><Table.Td colSpan={3 + stats.code_order.length}><Text c="dimmed">No tags with players yet.</Text></Table.Td></Table.Tr>
                  )}
                </Table.Tbody>
              </Table>
            </div>
          </Paper>
        </>
      )}
    </Stack>
  );
}
