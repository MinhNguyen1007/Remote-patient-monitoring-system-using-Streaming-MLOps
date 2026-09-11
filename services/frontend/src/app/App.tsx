import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { HomeRedirect, RequireAuth, RequireRole } from '@/app/routes';
import { AppShell } from '@/components/layout';
import { AuthProvider } from '@/context/AuthContext';
import { WebSocketProvider } from '@/context/WebSocketContext';
import { AlertsPage } from '@/pages/AlertsPage';
import { AssignmentsPage } from '@/pages/admin/AssignmentsPage';
import { ModelsPage } from '@/pages/admin/ModelsPage';
import { ThresholdsPage } from '@/pages/admin/ThresholdsPage';
import { UsersPage } from '@/pages/admin/UsersPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { LoginPage } from '@/pages/LoginPage';
import { PatientDetailPage } from '@/pages/PatientDetailPage';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <WebSocketProvider>
              <AppShell />
            </WebSocketProvider>
          </RequireAuth>
        }
      >
        <Route index element={<HomeRedirect />} />
        <Route element={<RequireRole roles={['DOCTOR', 'NURSE']} />}>
          <Route path="patients" element={<DashboardPage />} />
          <Route path="patients/:patientId" element={<PatientDetailPage />} />
          <Route path="alerts" element={<AlertsPage />} />
        </Route>
        <Route element={<RequireRole roles={['ADMIN']} />}>
          <Route path="admin/users" element={<UsersPage />} />
          <Route path="admin/assignments" element={<AssignmentsPage />} />
          <Route path="admin/thresholds" element={<ThresholdsPage />} />
          <Route path="admin/models" element={<ModelsPage />} />
        </Route>
        <Route path="*" element={<HomeRedirect />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
