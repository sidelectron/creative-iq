import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { MessageCircle } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { ChatPanel } from "./ChatPanel";
import { useBrand } from "../../contexts/BrandContext";

const titles: Record<string, string> = {
  "/": "Dashboard",
  "/ads": "Ads",
  "/profile": "Profile",
  "/tests": "A/B Tests",
  "/timeline": "Timeline",
  "/briefs": "Briefs",
  "/settings": "Settings",
  "/brands/new": "New Brand",
  "/onboarding": "Onboarding",
  "/account": "Account",
};

export function AppShell(): React.ReactElement {
  const [collapsed, setCollapsed] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const { brandId } = useBrand();
  const loc = useLocation();
  const title =
    titles[loc.pathname] ??
    (loc.pathname.startsWith("/ads/") ? "Ad detail" : "CreativeIQ");

  return (
    <div className="flex h-screen min-h-0 w-full overflow-hidden bg-slate-50">
      <div className={collapsed ? "w-16 shrink-0" : "w-56 shrink-0"}>
        <Sidebar collapsed={collapsed} onToggleCollapse={() => setCollapsed((c) => !c)} />
      </div>
      {/* Main + chat share horizontal space so main column shrinks when chat is open (lg+) */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col lg:flex-row">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col transition-[flex] duration-200">
          <TopBar
            title={title}
            chatOpen={chatOpen}
            onOpenChat={() => setChatOpen((o) => !o)}
          />
          <main className="min-h-0 flex-1 overflow-y-auto p-4">
            <Outlet />
          </main>
        </div>
        {chatOpen && (
          <div className="hidden h-full w-[min(38vw,36rem)] max-w-xl shrink-0 border-l border-slate-200 lg:flex lg:flex-col">
            <ChatPanel brandId={brandId} onClose={() => setChatOpen(false)} />
          </div>
        )}
        {chatOpen && (
          <div className="fixed inset-0 z-50 flex flex-col bg-white lg:hidden">
            <ChatPanel brandId={brandId} onClose={() => setChatOpen(false)} />
          </div>
        )}
      </div>
      {!chatOpen && (
        <button
          type="button"
          className="fixed bottom-6 right-6 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-white shadow-lg transition-transform hover:scale-105"
          onClick={() => setChatOpen(true)}
          aria-label="Open chat"
        >
          <MessageCircle className="h-7 w-7" />
        </button>
      )}
    </div>
  );
}
