import { NavLink } from "react-router-dom";
import {
  BarChart3,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FileText,
  Home,
  Image,
  LayoutDashboard,
  Plus,
  Settings,
  TestTube2,
} from "lucide-react";
import { useBrand } from "../../contexts/BrandContext";
import { clsx } from "clsx";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/ads", label: "Ads", icon: Image },
  { to: "/profile", label: "Profile", icon: BarChart3 },
  { to: "/tests", label: "Tests", icon: TestTube2 },
  { to: "/timeline", label: "Timeline", icon: ClipboardList },
  { to: "/briefs", label: "Briefs", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
];

type Props = {
  collapsed: boolean;
  onToggleCollapse: () => void;
};

export function Sidebar({ collapsed, onToggleCollapse }: Props): React.ReactElement {
  const { brands, brandId, setBrandId } = useBrand();

  return (
    <nav
      className={clsx(
        "flex h-full flex-col border-r border-slate-200 bg-primary text-primary-foreground transition-[width] duration-200",
        collapsed ? "w-16" : "w-56",
      )}
    >
      <div className="flex items-center justify-between p-2">
        {!collapsed && <span className="text-cardtitle px-2">CreativeIQ</span>}
        <button
          type="button"
          onClick={onToggleCollapse}
          className="rounded p-1 hover:bg-white/10"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
        </button>
      </div>
      <div className="border-b border-white/10 px-2 py-2">
        {!collapsed && <p className="text-datalabel text-slate-400">Brand</p>}
        <select
          className="mt-1 w-full rounded border border-white/20 bg-slate-800 px-2 py-1 text-datalabel"
          value={brandId ?? ""}
          onChange={(e) => setBrandId(e.target.value || null)}
          title="Switch brand"
        >
          {brands.length === 0 ? (
            <option value="">—</option>
          ) : (
            brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))
          )}
        </select>
      </div>
      <ul className="flex-1 space-y-1 p-2">
        {nav.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2 rounded px-2 py-2 text-datalabel hover:bg-white/10",
                  isActive && "bg-white/15 font-medium",
                )
              }
            >
              <Icon className="h-5 w-5 shrink-0" aria-hidden />
              {!collapsed && label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="border-t border-white/10 p-2">
        <NavLink
          to="/brands/new"
          className="flex items-center gap-2 rounded px-2 py-2 text-datalabel hover:bg-white/10"
        >
          <Plus className="h-5 w-5 shrink-0" />
          {!collapsed && "New Brand"}
        </NavLink>
        <NavLink
          to="/onboarding"
          className="mt-1 flex items-center gap-2 rounded px-2 py-2 text-datalabel hover:bg-white/10"
        >
          <Home className="h-5 w-5 shrink-0" />
          {!collapsed && "Onboarding"}
        </NavLink>
      </div>
    </nav>
  );
}
