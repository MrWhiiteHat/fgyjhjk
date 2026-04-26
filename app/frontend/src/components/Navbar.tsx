"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/predict/image", label: "Predict Image" },
  { href: "/predict/video", label: "Predict Video" },
  { href: "/explain", label: "Explain" },
  { href: "/reports", label: "Reports" }
];

export function Navbar(): React.JSX.Element {
  const pathname = usePathname();

  return (
    <nav className="navbar" aria-label="Main navigation">
      <div className="navbarBrand">RealFake Console</div>
      <ul className="navbarLinks">
        {links.map((item) => {
          const active = pathname === item.href;
          return (
            <li key={item.href}>
              <Link href={item.href} className={active ? "navLink navLinkActive" : "navLink"}>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
