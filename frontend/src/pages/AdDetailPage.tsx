import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Line,
  LineChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";
import {
  GROUP_LABELS,
  GROUP_ORDER,
  fingerprintGroupForKey,
} from "../lib/fingerprintGroups";
import {
  extractPaletteColors,
  isContinuousFingerprintValue,
  isLikelyEnumValue,
} from "../lib/normalizeFingerprint";

type Perf = {
  id: string;
  date: string;
  impressions: number;
  clicks: number;
  spend: string;
  revenue: string;
  video_views: number;
  video_completions: number;
  engagement_count: number;
};

type Detail = {
  id: string;
  title: string | null;
  platform: string;
  status: string;
  signed_video_url: string | null;
  performances: Perf[];
  fingerprint: { attributes: Record<string, unknown> } | null;
};

type AdRow = { id: string; title: string | null };
type Paginated<T> = { items: T[] };

export function AdDetailPage(): React.ReactElement {
  const { adId } = useParams<{ adId: string }>();
  const { brandId } = useBrand();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"overview" | "fingerprint" | "performance">("overview");
  const [compareId, setCompareId] = useState<string>("");
  const [metric, setMetric] = useState<"impressions" | "clicks" | "spend">("impressions");

  const detailQ = useQuery({
    queryKey: ["ad", brandId, adId],
    queryFn: async () => {
      const { data } = await api.get<Detail>(`/api/v1/brands/${brandId}/ads/${adId}`);
      return data;
    },
    enabled: !!brandId && !!adId,
    refetchInterval: (q) => (q.state.data?.status === "decomposing" ? 3000 : false),
  });

  const statusQ = useQuery({
    queryKey: ["ad-status", adId],
    queryFn: async () => {
      const { data } = await api.get<{ status: string }>(`/api/v1/ads/${adId}/status`);
      return data;
    },
    enabled: !!adId && detailQ.data?.status !== "decomposed",
    refetchInterval: 4000,
  });

  const otherAdsQ = useQuery({
    queryKey: ["ads", brandId, "pick"],
    queryFn: async () => {
      const { data } = await api.get<Paginated<AdRow>>(`/api/v1/brands/${brandId}/ads`, {
        params: { page: 1, page_size: 100 },
      });
      return data.items.filter((a) => a.id !== adId);
    },
    enabled: !!brandId && !!adId,
  });

  const chartData = useMemo(() => {
    const rows = detailQ.data?.performances ?? [];
    return rows
      .slice()
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((p) => ({
        date: p.date,
        impressions: p.impressions,
        clicks: p.clicks,
        spend: Number(p.spend),
      }));
  }, [detailQ.data]);

  const perfMut = useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      await api.post(`/api/v1/ads/${adId}/performance`, body);
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["ad", brandId, adId] }),
  });

  const bulkMut = useMutation({
    mutationFn: async (records: Record<string, unknown>[]) => {
      const { data } = await api.post<{ count: number }>(`/api/v1/ads/${adId}/performance/bulk`, {
        records,
      });
      return data;
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["ad", brandId, adId] }),
  });

  const [perfForm, setPerfForm] = useState({
    date: "",
    impressions: 0,
    clicks: 0,
    conversions: 0,
    spend: "0",
    revenue: "0",
    video_views: 0,
    video_completions: 0,
    engagement_count: 0,
  });
  const [csvPreview, setCsvPreview] = useState("");

  const fingerprintGroups = useMemo(() => {
    const attrs = detailQ.data?.fingerprint?.attributes ?? {};
    const map: Record<string, Record<string, unknown>> = {
      structural: {},
      visual: {},
      audio: {},
      content: {},
    };
    Object.entries(attrs).forEach(([k, v]) => {
      map[fingerprintGroupForKey(k)][k] = v as Record<string, unknown>;
    });
    return map;
  }, [detailQ.data]);

  if (!brandId || !adId) return <p>Missing ad.</p>;
  if (detailQ.isLoading) return <div className="h-64 animate-pulse rounded bg-slate-200" />;
  if (!detailQ.data) return <p>Not found.</p>;
  const ad = detailQ.data;
  const st = statusQ.data?.status ?? ad.status;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 border-b pb-2">
        {(["overview", "fingerprint", "performance"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`rounded px-3 py-1 capitalize ${
              tab === t ? "bg-accent text-white" : "bg-slate-100"
            }`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
        <Link to="/ads" className="ml-auto text-datalabel text-accent">
          ← Ads
        </Link>
      </div>

      {tab === "overview" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            {ad.signed_video_url ? (
              <video controls src={ad.signed_video_url} className="w-full rounded border" />
            ) : (
              <p className="text-muted">No signed URL</p>
            )}
            <p className="mt-2 text-body">
              {ad.title} · {ad.platform} · {st}
            </p>
            {(st === "ingested" || st === "decomposing") && (
              <p className="text-datalabel text-warn">Decomposition: {st}…</p>
            )}
          </div>
          <div>
            <h3 className="text-cardtitle">Performance trend</h3>
            <div className="mb-2">
              <select
                className="rounded border px-2 py-1 text-datalabel"
                value={metric}
                onChange={(e) => setMetric(e.target.value as typeof metric)}
              >
                <option value="impressions">Impressions</option>
                <option value="clicks">Clicks</option>
                <option value="spend">Spend</option>
              </select>
            </div>
            <div className="h-56 w-full">
              <ResponsiveContainer>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey={metric} stroke="#2563eb" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {tab === "fingerprint" && (
        <div className="space-y-6">
          {GROUP_ORDER.map((g) => (
            <section key={g}>
              <h3 className="text-section">{GROUP_LABELS[g]}</h3>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {Object.entries(fingerprintGroups[g]).map(([k, v]) => {
                  const colors = extractPaletteColors(v);
                  const enumLike = isLikelyEnumValue(v);
                  const cont = isContinuousFingerprintValue(v);
                  return (
                    <div key={k} className="rounded border bg-white p-3 text-datalabel">
                      <p className="font-medium text-slate-800">{k}</p>
                      {colors.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {colors.map((c) => (
                            <span
                              key={c}
                              className="h-8 w-8 rounded border border-slate-200 shadow-sm"
                              style={{ backgroundColor: c }}
                              title={c}
                            />
                          ))}
                        </div>
                      )}
                      {enumLike && (
                        <span className="mt-2 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium">
                          {typeof v === "string" ? v : JSON.stringify(v)}
                        </span>
                      )}
                      {cont && typeof v === "object" && v !== null && (
                        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-accent"
                            style={{
                              width: `${Math.min(100, Math.max(8, Number((v as { score?: number }).score ?? 0) * 100))}%`,
                            }}
                          />
                        </div>
                      )}
                      <pre className="mt-2 overflow-x-auto text-xs text-muted">
                        {JSON.stringify(v, null, 0)}
                      </pre>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}

      {tab === "performance" && (
        <div className="space-y-6">
          <div className="rounded border bg-white p-4">
            <h3 className="text-cardtitle">Manual row</h3>
            <form
              className="mt-2 grid gap-2 sm:grid-cols-2"
              onSubmit={(e) => {
                e.preventDefault();
                perfMut.mutate({
                  date: perfForm.date,
                  impressions: perfForm.impressions,
                  clicks: perfForm.clicks,
                  conversions: perfForm.conversions,
                  spend: perfForm.spend,
                  revenue: perfForm.revenue,
                  video_views: perfForm.video_views,
                  video_completions: perfForm.video_completions,
                  engagement_count: perfForm.engagement_count,
                });
              }}
            >
              <input
                type="date"
                required
                className="rounded border px-2 py-1"
                value={perfForm.date}
                onChange={(e) => setPerfForm((p) => ({ ...p, date: e.target.value }))}
              />
              <input
                type="number"
                placeholder="impressions"
                className="rounded border px-2 py-1"
                value={perfForm.impressions}
                onChange={(e) =>
                  setPerfForm((p) => ({ ...p, impressions: Number(e.target.value) }))
                }
              />
              <input
                type="number"
                placeholder="clicks"
                className="rounded border px-2 py-1"
                value={perfForm.clicks}
                onChange={(e) => setPerfForm((p) => ({ ...p, clicks: Number(e.target.value) }))}
              />
              <input
                type="number"
                placeholder="conversions"
                className="rounded border px-2 py-1"
                value={perfForm.conversions}
                onChange={(e) =>
                  setPerfForm((p) => ({ ...p, conversions: Number(e.target.value) }))
                }
              />
              <input
                placeholder="spend"
                className="rounded border px-2 py-1"
                value={perfForm.spend}
                onChange={(e) => setPerfForm((p) => ({ ...p, spend: e.target.value }))}
              />
              <input
                placeholder="revenue"
                className="rounded border px-2 py-1"
                value={perfForm.revenue}
                onChange={(e) => setPerfForm((p) => ({ ...p, revenue: e.target.value }))}
              />
              <input
                type="number"
                placeholder="video_views"
                className="rounded border px-2 py-1"
                value={perfForm.video_views}
                onChange={(e) =>
                  setPerfForm((p) => ({ ...p, video_views: Number(e.target.value) }))
                }
              />
              <input
                type="number"
                placeholder="video_completions"
                className="rounded border px-2 py-1"
                value={perfForm.video_completions}
                onChange={(e) =>
                  setPerfForm((p) => ({ ...p, video_completions: Number(e.target.value) }))
                }
              />
              <input
                type="number"
                placeholder="engagement_count"
                className="rounded border px-2 py-1"
                value={perfForm.engagement_count}
                onChange={(e) =>
                  setPerfForm((p) => ({ ...p, engagement_count: Number(e.target.value) }))
                }
              />
              <button type="submit" className="rounded bg-accent px-3 py-1 text-white">
                Save row
              </button>
            </form>
          </div>
          <div className="rounded border bg-white p-4">
            <h3 className="text-cardtitle">CSV / JSON bulk (preview)</h3>
            <p className="text-datalabel text-muted">
              Paste JSON array of records matching API fields (date, impressions, clicks, …).
            </p>
            <textarea
              className="mt-2 w-full rounded border font-mono text-xs"
              rows={6}
              value={csvPreview}
              onChange={(e) => setCsvPreview(e.target.value)}
              placeholder='[{"date":"2024-01-01","impressions":100,"clicks":2,...}]'
            />
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                className="rounded border px-3 py-1 text-datalabel"
                onClick={() => {
                  try {
                    const parsed = JSON.parse(csvPreview) as Record<string, unknown>[];
                    if (!Array.isArray(parsed)) throw new Error("not array");
                    setCsvPreview(JSON.stringify(parsed, null, 2));
                  } catch {
                    alert("Invalid JSON");
                  }
                }}
              >
                Preview format
              </button>
              <button
                type="button"
                className="rounded bg-accent px-3 py-1 text-white"
                onClick={() => {
                  try {
                    const records = JSON.parse(csvPreview) as Record<string, unknown>[];
                    bulkMut.mutate(records);
                  } catch {
                    alert("Invalid JSON");
                  }
                }}
              >
                Import bulk
              </button>
              <a
                className="text-datalabel text-accent"
                href={`data:text/csv,date,impressions,clicks,conversions,spend,revenue,video_views,video_completions,engagement_count%0A2024-01-01,0,0,0,0,0,0,0,0`}
                download="performance-template.csv"
              >
                Download CSV template
              </a>
            </div>
          </div>
          <div className="rounded border bg-white p-4">
            <h3 className="text-cardtitle">Compare to second ad</h3>
            <select
              className="mt-2 rounded border px-2 py-1"
              value={compareId}
              onChange={(e) => setCompareId(e.target.value)}
            >
              <option value="">Pick an ad…</option>
              {(otherAdsQ.data ?? []).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.title ?? o.id}
                </option>
              ))}
            </select>
            {compareId && (
              <p className="mt-2">
                <Link className="text-accent" to={`/ads/compare?ids=${adId},${compareId}`}>
                  Open compare view
                </Link>
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
