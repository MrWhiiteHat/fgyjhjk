"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

const menuLinks = [
  { href: "/", label: "Dashboard", icon: "⊞" },
  { href: "/predict/image", label: "Predict Image", icon: "🖼️" },
  { href: "/predict/video", label: "Predict Video", icon: "🎬" },
  { href: "/explain", label: "Explain", icon: "🔍" },
  { href: "/reports", label: "Reports", icon: "📊" }
];

const generalLinks = [
  { href: "#", label: "Settings", icon: "⚙️" },
  { href: "#", label: "Help", icon: "❓" }
];

export function Sidebar(): React.JSX.Element {
  const pathname = usePathname();
  const { logout } = useAuth();

  return (
    <aside className="sidebar">
      <div className="sidebarBrand">
        <span>🛡️</span> RealFake
      </div>

      <div className="sidebarSection">
        <div className="sidebarLabel">Menu</div>
        <ul className="sidebarLinks">
          {menuLinks.map((item) => {
            const active = pathname === item.href;
            return (
              <li key={item.href}>
                <Link href={item.href} className={`navLink ${active ? "navLinkActive" : ""}`}>
                  <span>{item.icon}</span> {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="sidebarSection" style={{ flexGrow: 1 }}>
        <div className="sidebarLabel">General</div>
        <ul className="sidebarLinks">
          {generalLinks.map((item) => (
            <li key={item.label}>
              <a href={item.href} className="navLink">
                <span>{item.icon}</span> {item.label}
              </a>
            </li>
          ))}
          <li>
            <button onClick={logout} className="navLink" style={{ background: "none", border: "none", width: "100%", textAlign: "left", cursor: "pointer", font: "inherit" }}>
              <span>🚪</span> Logout
            </button>
          </li>
        </ul>
      </div>

      <div style={{ marginTop: "auto", background: "linear-gradient(135deg, var(--primary-dark), var(--primary))", borderRadius: "16px", padding: "1.2rem", color: "#fff", position: "relative", overflow: "hidden" }}>
        <h4 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem" }}>Download our Mobile App</h4>
        <p style={{ margin: "0 0 1rem 0", fontSize: "0.8rem", color: "rgba(255,255,255,0.8)" }}>Get easy in another way</p>
        <button style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "none", background: "rgba(255,255,255,0.2)", color: "#fff", fontWeight: "600", cursor: "pointer" }}>Download</button>
      </div>

    </aside>
  );
}
