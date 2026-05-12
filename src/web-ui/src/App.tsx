import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";

import { queryClient } from "@/lib/query";
import Landing from "./pages/Landing";
import NotFound from "./pages/NotFound";
import { AppShell } from "./components/app/AppShell";
import Overview from "./pages/app/Overview";
import CampaignsList from "./pages/app/CampaignsList";
import CampaignDetail from "./pages/app/CampaignDetail";
import CompaniesList from "./pages/app/CompaniesList";
import CompanyDetail from "./pages/app/CompanyDetail";
import DraftsList from "./pages/app/DraftsList";
import DraftDetail from "./pages/app/DraftDetail";
import Observability from "./pages/app/Observability";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<AppShell />}>
            <Route index element={<Overview />} />
            <Route path="campaigns" element={<CampaignsList />} />
            <Route path="campaigns/:id" element={<CampaignDetail />} />
            <Route path="companies" element={<CompaniesList />} />
            <Route path="companies/:id" element={<CompanyDetail />} />
            <Route path="drafts" element={<DraftsList />} />
            <Route path="drafts/:id" element={<DraftDetail />} />
            <Route path="observability" element={<Observability />} />
          </Route>
          <Route path="/login" element={<Navigate to="/app" replace />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
