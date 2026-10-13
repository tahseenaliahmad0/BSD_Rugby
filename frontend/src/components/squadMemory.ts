const KEY = 'rugby.lastSquadId';

export function rememberSquad(id: string): void {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* private mode or storage disabled: ignore */
  }
}

export function lastSquad(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
