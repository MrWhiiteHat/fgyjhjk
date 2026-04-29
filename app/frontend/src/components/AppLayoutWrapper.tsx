"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { ReactNode, useState } from "react";

export function AppLayoutWrapper({ children }: { children: ReactNode }): React.JSX.Element {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const pathname = usePathname();
  const isAuthPage = pathname === "/login" || pathname === "/signup";

  if (isAuthPage) {
    return (
      <main className="mainContainer" style={{ maxWidth: "100%", padding: "2rem" }}>
        {children}
      </main>
    );
  }

  return (
    <div className="appLayout">
      <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />
      <div className={`mainWrapper ${isSidebarOpen ? "sidebarOpen" : ""}`}>
        <Topbar toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />
        <main className="mainContainer">{children}</main>
      </div>
    </div>
  );
}
