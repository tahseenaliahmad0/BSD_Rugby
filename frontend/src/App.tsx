import { Navigate, Route, Routes } from 'react-router';
import { RequireAuth } from './auth/RequireAuth';
import { Shell } from './components/Shell';
import { HomeRedirect } from './pages/HomeRedirect';
import { LibraryPage } from './pages/LibraryPage';
import { LoginPage } from './pages/LoginPage';
import { MatchPage } from './pages/MatchPage';
import { NewMatchPage } from './pages/NewMatchPage';
import { DownloadsPage } from './pages/DownloadsPage';
import { FindClipsPage } from './pages/FindClipsPage';
import { PlaylistPage } from './pages/PlaylistPage';
import { PlaylistsPage } from './pages/PlaylistsPage';
import { StatsPage } from './pages/StatsPage';
import { TemplateEditorPage } from './pages/templates/TemplateEditorPage';
import { TemplatesPage } from './pages/templates/TemplatesPage';
import { TaggingPage } from './tagging/TaggingPage';

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
          <Route path="/matches/:eventId/tag" element={<TaggingPage />} />
          <Route path="/squads/:squadId/clips" element={<FindClipsPage />} />
          <Route path="/squads/:squadId/playlists" element={<PlaylistsPage />} />
          <Route path="/playlists/:playlistId" element={<PlaylistPage />} />
          <Route path="/squads/:squadId/stats" element={<StatsPage />} />
          <Route path="/squads/:squadId/downloads" element={<DownloadsPage />} />
          <Route path="/squads/:squadId/templates" element={<TemplatesPage />} />
          <Route path="/templates/:templateId" element={<TemplateEditorPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
