import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogOut, MessageCircle, Search, User } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";

type Props = {
  title: string;
  onOpenChat: () => void;
  chatOpen: boolean;
};

export function TopBar({ title, onOpenChat, chatOpen }: Props): React.ReactElement {
  const { user, logout } = useAuth();
  const [q, setQ] = useState("");
  const [menu, setMenu] = useState(false);
  const navigate = useNavigate();

  return (
    <header className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-3">
      <h1 className="text-section text-slate-900">{title}</h1>
      <form
        className="hidden max-w-md flex-1 md:block"
        onSubmit={(e) => {
          e.preventDefault();
          const t = q.trim();
          if (!t) return;
          const uuid =
            /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.exec(t)?.[0];
          if (uuid) navigate(`/ads/${uuid}`);
          else if (/^fp:/i.test(t)) {
            const needle = t.replace(/^fp:/i, "").trim();
            if (needle) navigate(`/ads?fpq=${encodeURIComponent(needle)}`);
          } else navigate(`/ads?q=${encodeURIComponent(t)}`);
        }}
      >
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted" aria-hidden />
          <input
            className="w-full rounded border border-slate-300 py-2 pl-8 pr-3 text-datalabel focus:border-accent focus:outline-none"
            placeholder="Title search · paste ad UUID · fp:text for fingerprint…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </form>
      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenChat}
          className={[
            "rounded-full p-2 lg:hidden",
            chatOpen ? "bg-accent text-white" : "bg-slate-100",
          ].join(" ")}
          aria-label="Toggle chat"
        >
          <MessageCircle className="h-5 w-5" />
        </button>
        <div className="relative">
          <button
            type="button"
            className="flex items-center gap-2 rounded border border-slate-200 px-2 py-1 text-datalabel hover:bg-slate-50"
            onClick={() => setMenu(!menu)}
          >
            <User className="h-4 w-4" />
            {user?.full_name ?? user?.email}
          </button>
          {menu && (
            <div className="absolute right-0 z-50 mt-1 w-44 rounded border border-slate-200 bg-white py-1 shadow">
              <Link
                to="/account"
                className="block px-3 py-2 text-datalabel hover:bg-slate-50"
                onClick={() => setMenu(false)}
              >
                Profile
              </Link>
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-datalabel hover:bg-slate-50"
                onClick={() => {
                  logout();
                  setMenu(false);
                  navigate("/login");
                }}
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
