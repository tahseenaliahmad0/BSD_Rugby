import {
  AppShell,
  Button,
  Container,
  Group,
  Menu,
  Modal,
  Select,
  Text,
  UnstyledButton,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconChevronDown, IconLogout, IconPlus, IconUser } from '@tabler/icons-react';
import { NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router';
import { useLogout, useSquads } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';
import { CreateSquadForm } from './CreateSquadForm';
import { lastSquad, rememberSquad } from './squadMemory';

export function Shell() {
  const { me, canEdit } = useAuth();
  const { squadId: squadParam } = useParams();
  const { data: squads } = useSquads();
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useLogout();
  const [newSquadOpen, newSquad] = useDisclosure(false);

  const options = (squads ?? []).map((s) => ({ value: s.id, label: s.name }));
  const squadId = squadParam ?? lastSquad() ?? options[0]?.value ?? null;
  const nav = squadId
    ? [
        { to: `/squads/${squadId}`, label: 'Library', end: true },
        { to: `/squads/${squadId}/clips`, label: 'Find clips' },
        { to: `/squads/${squadId}/playlists`, label: 'Playlists' },
        { to: `/squads/${squadId}/stats`, label: 'Stats' },
        { to: `/squads/${squadId}/downloads`, label: 'Downloads' },
        ...(canEdit(squadId) ? [{ to: `/squads/${squadId}/templates`, label: 'Templates' }] : []),
      ]
    : [];

  return (
    <AppShell header={{ height: 64 }} padding="md">
      <AppShell.Header>
        <Container size="xl" h="100%">
          <Group h="100%" justify="space-between" wrap="nowrap" gap="sm">
            <Group gap="sm" wrap="nowrap">
              <UnstyledButton onClick={() => navigate('/')} aria-label="Home" className="brand">
                <Text fw={800} size="xl" c="green.8" style={{ whiteSpace: 'nowrap' }}>
                  <span className="brand-long">Rugby Video</span>
                  <span className="brand-short">RV</span>
                </Text>
              </UnstyledButton>
              {options.length > 0 && (
                <Select
                  aria-label="Squad"
                  data-testid="squad-switcher"
                  data={options}
                  value={squadId ?? null}
                  placeholder="Choose a squad"
                  allowDeselect={false}
                  onChange={(id) => {
                    if (id) {
                      rememberSquad(id);
                      navigate(`/squads/${id}`);
                    }
                  }}
                  w={180}
                  size="sm"
                  className="squad-switcher"
                  comboboxProps={{ withinPortal: true }}
                />
              )}
              <nav className="main-nav" aria-label="Main">
                {nav.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `main-nav-link${isActive || (item.end && location.pathname.startsWith('/matches/')) ? ' active' : ''}`
                    }
                    data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </Group>
            <Menu position="bottom-end" width={220}>
              <Menu.Target>
                <Button variant="subtle" leftSection={<IconUser size={20} />} rightSection={<IconChevronDown size={16} />} data-testid="user-menu">
                  {me.name}
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>{me.email}</Menu.Label>
                {me.is_superadmin && (
                  <Menu.Item leftSection={<IconPlus size={18} />} onClick={newSquad.open} data-testid="new-squad">
                    New squad
                  </Menu.Item>
                )}
                <Menu.Item
                  leftSection={<IconLogout size={18} />}
                  onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
                  data-testid="logout"
                >
                  Sign out
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Container>
      </AppShell.Header>
      <AppShell.Main>
        <Container size="xl">
          <Outlet />
        </Container>
      </AppShell.Main>
      <Modal opened={newSquadOpen} onClose={newSquad.close} title="New squad">
        {newSquadOpen && <CreateSquadForm onDone={newSquad.close} />}
      </Modal>
    </AppShell>
  );
}
