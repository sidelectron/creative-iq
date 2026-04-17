import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "../contexts/AuthContext";
import { LoginPage } from "../pages/LoginPage";
import { AdsPage } from "../pages/AdsPage";
import { BrandProvider } from "../contexts/BrandContext";
import { ProfilePage } from "../pages/ProfilePage";
import { ABWizardPage } from "../pages/ABWizardPage";
import { ChatPanel } from "../components/layout/ChatPanel";
import type { ChatMessage } from "../hooks/useChatWebSocket";

const apiGet = vi.fn();
const apiPost = vi.fn();

const tokenStore = { access: null as string | null };

vi.mock("../lib/api", () => {
  const chain = {
    get: (...args: unknown[]) => apiGet(...args),
    post: (...args: unknown[]) => apiPost(...args),
    delete: vi.fn(),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  };
  return {
    api: chain,
    getStoredAccessToken: () => tokenStore.access,
    setTokens: vi.fn((a: string) => {
      tokenStore.access = a;
    }),
    clearTokens: vi.fn(() => {
      tokenStore.access = null;
    }),
  };
});

vi.mock("../hooks/useChatWebSocket", () => ({
  useChatWebSocket: vi.fn(() => ({
    statusMessage: null,
    messages: [
      { id: "1", role: "user", content: "Hello" },
      { id: "2", role: "assistant", content: "See [profile](/profile) for more." },
    ] as ChatMessage[],
    followups: [],
    busy: false,
    send: vi.fn(),
    sendSubscribeGeneration: vi.fn(),
    connected: true,
    resetThread: vi.fn(),
    selectConversation: vi.fn(),
  })),
}));

function qc(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

describe("Phase 8 RTL (plan Step 12)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    tokenStore.access = null;
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it("login: successful login redirects away from /login", async () => {
    apiGet.mockImplementation(async (url: string) => {
      if (url === "/api/v1/auth/me") {
        if (!tokenStore.access) {
          const err = new Error("unauthorized") as Error & { response?: { status: number } };
          err.response = { status: 401 };
          throw err;
        }
        return {
          data: {
            id: "u1",
            email: "a@b.com",
            full_name: "Test User",
            is_active: true,
          },
        };
      }
      return { data: {} };
    });
    apiPost.mockImplementation(async (url: string) => {
      if (url === "/api/v1/auth/login") {
        return {
          data: {
            access_token: "at",
            refresh_token: "rt",
            token_type: "bearer",
          },
        };
      }
      return { data: {} };
    });

    function PostLogin(): React.ReactElement {
      const { isAuthenticated } = useAuth();
      if (!isAuthenticated) return <LoginPage />;
      return <p>Dashboard</p>;
    }

    render(
      <QueryClientProvider client={qc()}>
        <MemoryRouter initialEntries={[{ pathname: "/login", state: { from: "/dashboard" } }]}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<PostLogin />} />
              <Route path="/dashboard" element={<p>Dashboard</p>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: /Sign in/i }));

    await waitFor(() => expect(screen.getByText("Dashboard")).toBeInTheDocument());
  });

  it("ads: drop files triggers upload POST", async () => {
    tokenStore.access = "logged-in";
    sessionStorage.setItem("ci_selected_brand_id", "brand-1");
    apiGet.mockImplementation(async (url: string) => {
      const path = url.split("?")[0];
      if (path === "/api/v1/auth/me") {
        return {
          data: { id: "u1", email: "t@test.com", full_name: "Tester", is_active: true },
        };
      }
      if (path === "/api/v1/brands") {
        return { data: { items: [{ id: "brand-1", name: "B", industry: null, created_at: "", role: "editor" }] } };
      }
      if (path.endsWith("/ads")) {
        return { data: { items: [], total: 0, page: 1, page_size: 50 } };
      }
      return { data: {} };
    });
    apiPost.mockResolvedValue({ data: {} });

    render(
      <QueryClientProvider client={qc()}>
        <MemoryRouter initialEntries={["/ads"]}>
          <AuthProvider>
            <BrandProvider>
              <Routes>
                <Route path="/ads" element={<AdsPage />} />
              </Routes>
            </BrandProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText(/Drag and drop video files here/i)).toBeInTheDocument());

    const zone = screen.getByText(/Drag and drop video files here/i).closest("div");
    expect(zone).toBeTruthy();
    const file = new File(["x"], "clip.mp4", { type: "video/mp4" });
    fireEvent.drop(zone!, { dataTransfer: { files: [file] } });

    await waitFor(() =>
      expect(apiPost).toHaveBeenCalledWith(
        "/api/v1/brands/brand-1/ads/upload",
        expect.any(FormData),
        expect.objectContaining({ headers: { "Content-Type": "multipart/form-data" } }),
      ),
    );
  });

  it("profile: categorical scorecards render swatches from mocked profile", async () => {
    tokenStore.access = "logged-in";
    sessionStorage.setItem("ci_selected_brand_id", "brand-1");
    apiGet.mockImplementation(async (url: string) => {
      const path = url.split("?")[0];
      if (path === "/api/v1/auth/me") {
        return {
          data: { id: "u1", email: "t@test.com", full_name: "Tester", is_active: true },
        };
      }
      if (path === "/api/v1/brands") {
        return { data: { items: [{ id: "brand-1", name: "B", industry: null, created_at: "", role: "editor" }] } };
      }
      if (path.endsWith("/profile")) {
        return {
          data: {
            profile: {
              categorical: {
                hook_type: {
                  story: { score: 0.8, confidence: 0.7, n: 12 },
                  product: { score: 0.2, confidence: 0.6, n: 4 },
                },
              },
              recommendations: [],
            },
            highlights: [],
            data_health: {},
          },
        };
      }
      return { data: {} };
    });

    render(
      <QueryClientProvider client={qc()}>
        <MemoryRouter>
          <AuthProvider>
            <BrandProvider>
              <ProfilePage />
            </BrandProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const card = await screen.findByTestId("profile-scorecard-hook_type");
    expect(card).toBeInTheDocument();
    fireEvent.click(card.querySelector("summary")!);
    expect(await screen.findAllByTestId("profile-scorecard-swatch")).toHaveLength(2);
  });

  it("chat: assistant bubble uses alignment + markdown link", async () => {
    apiGet.mockImplementation(async (url: string) => {
      if (url.includes("/chat/conversations")) {
        return { data: { items: [] } };
      }
      return { data: {} };
    });
    render(
      <QueryClientProvider client={qc()}>
        <MemoryRouter>
          <Routes>
            <Route path="/" element={<ChatPanel brandId="brand-1" onClose={() => {}} />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("Hello")).toBeInTheDocument());
    const userBubble = screen.getByText("Hello").closest(".flex");
    expect(userBubble?.className).toMatch(/justify-end/);
    expect(screen.getByRole("link", { name: /profile/i })).toHaveAttribute("href", "/profile");
  });

  it("A/B wizard review shows numeric preview from preview-design API", async () => {
    tokenStore.access = "logged-in";
    sessionStorage.setItem("ci_selected_brand_id", "brand-1");
    apiGet.mockImplementation(async (url: string) => {
      const path = url.split("?")[0];
      if (path === "/api/v1/auth/me") {
        return {
          data: { id: "u1", email: "t@test.com", full_name: "Tester", is_active: true },
        };
      }
      if (path === "/api/v1/brands") {
        return { data: { items: [{ id: "brand-1", name: "B", industry: null, created_at: "", role: "editor" }] } };
      }
      return { data: {} };
    });
    apiPost.mockImplementation(async (url: string) => {
      if (url.includes("preview-design")) {
        return {
          data: {
            sample_size_per_variant: 1250,
            estimated_budget_per_variant: 15.0,
            estimated_duration_days: 3,
            hypothesis: "h",
            alpha: 0.05,
            power: 0.8,
            mde_relative: 0.1,
            mde_absolute: 0.002,
          },
        };
      }
      return { data: {} };
    });

    render(
      <QueryClientProvider client={qc()}>
        <MemoryRouter>
          <AuthProvider>
            <BrandProvider>
              <ABWizardPage />
            </BrandProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    for (let i = 0; i < 3; i++) {
      fireEvent.click(await screen.findByRole("button", { name: /Next/i }));
    }

    await waitFor(() => expect(screen.getByTestId("ab-design-preview")).toHaveTextContent("1,250"));
    expect(screen.getByTestId("ab-design-preview")).toHaveTextContent("$15.00");
    expect(screen.getByTestId("ab-design-preview")).toHaveTextContent("3 days");
  });

  it("unauthenticated gate shows login route content", () => {
    function Gate(): React.ReactElement {
      const { isAuthenticated, loading } = useAuth();
      if (loading) return <div>loading</div>;
      if (!isAuthenticated) return <Navigate to="/login" replace />;
      return <div>in</div>;
    }
    render(
      <QueryClientProvider client={qc()}>
        <MemoryRouter initialEntries={["/"]}>
          <AuthProvider>
            <Routes>
              <Route path="/" element={<Gate />} />
              <Route path="/login" element={<LoginPage />} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("heading", { name: /Sign in/i })).toBeInTheDocument();
  });
});
