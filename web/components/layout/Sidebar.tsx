"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "🏠" },
  { href: "/discover", label: "Discover", icon: "🔍" },
  { href: "/clubs", label: "Clubs", icon: "🎓" },
  { href: "/events", label: "Events", icon: "📅" },
  { href: "/subscriptions", label: "Subscriptions", icon: "🔔" },
  { href: "/digest", label: "Digest", icon: "📬" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside
      className="w-56 h-full flex flex-col"
      style={{ background: "var(--bg-sidebar)" }}
    >
      <div className="px-4 py-5 border-b border-white/10">
        <span className="text-white font-bold text-lg">S.E.E.R. 🏴</span>
        <p className="text-white/40 text-xs mt-0.5">Rutgers Events Agent</p>
      </div>
      <nav className="flex-1 py-4 space-y-0.5 px-2">
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
                ${
                  active
                    ? "bg-white/10 text-white font-medium border-l-2 border-[var(--primary)]"
                    : "text-white/60 hover:bg-white/5 hover:text-white"
                }`}
            >
              <span>{icon}</span>
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
