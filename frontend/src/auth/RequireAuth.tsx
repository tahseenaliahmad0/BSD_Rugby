import { Center, Loader } from '@mantine/core';
import { useMemo } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router';
import { useMe } from '../api/hooks';
import type { Role } from '../api/types';
import { AuthContext, EDIT_ROLES } from './AuthContext';

export function RequireAuth() {
  const { data: me, isPending, isError } = useMe();
  const location = useLocation();

  const value = useMemo(() => {
    if (!me) return null;
    const roleIn = (squadId: string): Role | null => {
      if (me.is_superadmin) return 'admin';
      return me.memberships.find((m) => m.squad_id === squadId)?.role ?? null;
    };
    return {
      me,
      roleIn,
      canEdit: (squadId: string) => {
        const role = roleIn(squadId);
        return role !== null && EDIT_ROLES.has(role);
      },
    };
  }, [me]);

  if (isPending) {
    return (
      <Center h="100vh">
        <Loader size="lg" />
      </Center>
    );
  }
  if (isError || !me || !value) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return (
    <AuthContext.Provider value={value}>
      <Outlet />
    </AuthContext.Provider>
  );
}
