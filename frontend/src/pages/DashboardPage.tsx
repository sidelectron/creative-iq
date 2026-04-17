import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

type Paginated<T> = { items: T[]; total: number };

export function DashboardPage(): React.ReactElement {
  const { brandId, brands, brandsLoading } = useBrand();

  const adsQ = useQuery({
    queryKey: ["ads", brandId, "dash"],
    queryFn: async () => {
      const { data } = await api.get<Paginated<{ id: string }>>(
        `/api/v1/brands/${brandId}/ads`,
        { params: { page: 1, page_size: 1 } },
      );
      return data;
    },
    enabled: !!brandId,
  });

  const profileQ = useQuery({
    queryKey: ["profile", brandId],
    queryFn: async () => {
      const { data } = await api.get("/api/v1/brands/" + brandId + "/profile");
      return data as { data_health?: { computed_at?: string } };
    },
    enabled: !!brandId,
    retry: false,
  });

  const driftQ = useQuery({
    queryKey: ["drift", brandId],
    queryFn: async () => {
      const { data } = await api.get<unknown[]>(`/api/v1/brands/${brandId}/drift`);
      return data.length;
    },
    enabled: !!brandId,
    retry: false,
  });

  const openTestsQ = useQuery({
    queryKey: ["ab-tests-dash", brandId],
    queryFn: async () => {
      const { data } = await api.get<{ items: { status: string }[] }>(
        `/api/v1/brands/${brandId}/tests`,
        { params: { page: 1, page_size: 100 } },
      );
      return data.items.filter((t) => t.status === "proposed" || t.status === "active").length;
    },
    enabled: !!brandId,
    retry: false,
  });

  if (!brandsLoading && brands.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center">
        <h2 className="text-section">Create your first brand</h2>
        <p className="mt-2 text-body text-muted">Get started with CreativeIQ.</p>
        <Link
          to="/brands/new"
          className="mt-4 inline-block rounded bg-accent px-4 py-2 text-white"
        >
          New brand
        </Link>
      </div>
    );
  }

  if (!brandId) {
    return <div className="animate-pulse h-24 rounded bg-slate-200" />;
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-datalabel text-muted">Ads</p>
          {adsQ.isLoading ? (
            <div className="mt-2 h-8 w-16 animate-pulse rounded bg-slate-100" />
          ) : (
            <p className="text-page text-slate-900">{adsQ.data?.total ?? 0}</p>
          )}
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-datalabel text-muted">Profile</p>
          {profileQ.isLoading ? (
            <div className="mt-2 h-8 w-32 animate-pulse rounded bg-slate-100" />
          ) : profileQ.isError ? (
            <p className="text-datalabel text-muted">No profile yet</p>
          ) : (
            <p className="text-datalabel text-success">Available</p>
          )}
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-datalabel text-muted">Drift alerts</p>
          {driftQ.isLoading ? (
            <div className="mt-2 h-8 w-12 animate-pulse rounded bg-slate-100" />
          ) : driftQ.isError ? (
            <p className="text-datalabel text-muted">—</p>
          ) : (
            <p className="text-page text-slate-900">{driftQ.data ?? 0}</p>
          )}
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-datalabel text-muted">Open A/B tests</p>
          {openTestsQ.isLoading ? (
            <div className="mt-2 h-8 w-12 animate-pulse rounded bg-slate-100" />
          ) : (
            <p className="text-page text-slate-900">{openTestsQ.data ?? 0}</p>
          )}
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 sm:col-span-2 lg:col-span-1">
          <p className="text-datalabel text-muted">Quick links</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Link className="text-datalabel text-accent hover:underline" to="/ads">
              Ads
            </Link>
            <Link className="text-datalabel text-accent hover:underline" to="/tests">
              Tests
            </Link>
            <Link className="text-datalabel text-accent hover:underline" to="/briefs">
              Briefs
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
