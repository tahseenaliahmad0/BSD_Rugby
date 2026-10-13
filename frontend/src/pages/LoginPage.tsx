import { Alert, Button, Center, Paper, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router';
import { ApiError } from '../api/client';
import { useLogin, useMe } from '../api/hooks';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const login = useLogin();
  const { data: me } = useMe();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/';

  if (me) return <Navigate to={from} replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate({ email: email.trim(), password }, { onSuccess: () => navigate(from, { replace: true }) });
  };

  const message =
    login.error instanceof ApiError
      ? login.error.detail
      : login.error
        ? 'Could not reach the server. Check the network and try again.'
        : null;

  return (
    <Center mih="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" radius="md" w={420} maw="100%">
        <form onSubmit={submit}>
          <Stack gap="md">
            <div>
              <Title order={2}>Rugby Video</Title>
              <Text c="dimmed">Sign in to watch and tag footage.</Text>
            </div>
            <TextInput
              label="Email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.currentTarget.value)}
              data-testid="login-email"
            />
            <PasswordInput
              label="Password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              data-testid="login-password"
            />
            {message && (
              <Alert color="red" icon={<IconAlertCircle size={18} />} data-testid="login-error">
                {message}
              </Alert>
            )}
            <Button type="submit" size="lg" loading={login.isPending} data-testid="login-submit">
              Sign in
            </Button>
          </Stack>
        </form>
      </Paper>
    </Center>
  );
}
