"use client";

import { useAuth } from "@/components/AuthProvider";

export function Topbar(): React.JSX.Element {
  const { user } = useAuth();

  return (
    <header className="topbar">
      <div className="searchBar">
        <span style={{ color: "var(--muted)" }}>🔍</span>
        <input type="text" placeholder="Search scan..." />
      </div>

      <div className="topbarActions">
        <button className="iconBtn">✉️</button>
        <button className="iconBtn">🔔</button>
        
        <div className="userProfile">
          <img src="https://ui-avatars.com/api/?name=Admin+User&background=random" alt="User Avatar" />
          <div className="userInfo">
            <span className="name">{user?.full_name || "Admin User"}</span>
            <span className="role">{user?.email || "admin@realfake.com"}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
