import { createContext, useContext } from 'react';
import type { Me, Role } from '../api/types';

export interface AuthState {
  me: Me;
  /** The user's role in a squad, or null when they are not a member. Superadmins are admins. */
  roleIn: (squadId: string) => Role | null;
  canEdit: (squadId: string) => boolean;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside RequireAuth');
  return value;
}

export const EDIT_ROLES: ReadonlySet<Role> = new Set(['admin', 'analyst']);
