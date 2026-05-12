import { Outlet } from "react-router-dom";

import { Sidebar } from "./Sidebar";

export function AppShell() {
  return (
    <div className="min-h-screen flex bg-neutral-50 text-black">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden">
        <div className="max-w-6xl mx-auto px-6 md:px-10 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
