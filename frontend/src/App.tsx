import { Navigate, Route, Routes } from 'react-router';
import { RequireAuth } from './auth/RequireAuth';
import { Shell } from './components/Shell';
import { HomeRedirect } from './pages/HomeRedirect';
import { LibraryPage } from './pages/LibraryPage';
import { LoginPage } from './pages/LoginPage';
import { MatchPage } from './pages/MatchPage';
import { NewMatchPage } from './pages/NewMatchPage';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route index element={<HomeRedirect />} />
          <Route path="/squads/:squadId" element={<LibraryPage />} />
          <Route path="/squads/:squadId/matches/new" element={<NewMatchPage />} />
          <Route path="/matches/:eventId" element={<MatchPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
