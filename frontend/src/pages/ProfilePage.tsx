import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

type ProfilePayload = {
  profile: Record<string, unknown> & {
    platforms?: Record<string, Record<string, unknown>>;
    categorical?: Record<string, Record<string, { score?: number; confidence?: number; n?: number }>>;
    continuous?: Record<string, Record<string, unknown>>;
    recommendations?: unknown[];
    computed_at?: string;
    total_ads_analyzed?: number;
    context?: { current_era_hint?: { title?: string } | null };
  };
  highlights: unknown[];
  data_health: Record<string, unknown>;
};

export function ProfilePage(): React.ReactElement {
  const { brandId } = useBrand();
  const [platform, setPlatform] = useState<string>("");

  const q = useQuery({
    queryKey: ["profile", brandId, platform || "all"],
    queryFn: async () => {
      const { data } = await api.get<ProfilePayload>("/api/v1/brands/" + brandId + "/profile", {
        params: platform ? { platform } : {},
      });
      return data;
    },
    enabled: !!brandId,
    retry: false,
  });

  const platforms = useMemo(() => {
    const prof = q.data?.profile;
    if (!prof) return [];
    if (prof.platforms && typeof prof.platforms === "object") {
      return Object.keys(prof.platforms as Record<string, unknown>);
    }
    return [];
  }, [q.data]);

  const selectedProfile = useMemo(() => {
    const prof = q.data?.profile;
    if (!prof) return null;
    if (platform && prof.platforms && (prof.platforms as Record<string, unknown>)[platform]) {
      return (prof.platforms as Record<string, Record<string, unknown>>)[platform];
    }
    if (!platform && !prof.platforms) return prof as Record<string, unknown>;
    if (!platform && prof.platforms) {
      const first = Object.keys(prof.platforms)[0];
      return first
        ? (prof.platforms as Record<string, Record<string, unknown>>)[first]
        : (prof as Record<string, unknown>);
    }
    return prof as Record<string, unknown>;
  }, [q.data, platform]);

  const categorical = useMemo(() => {
    return (selectedProfile?.categorical ?? {}) as Record<
      string,
      Record<string, { score?: number; confidence?: number; n?: number }>
    >;
  }, [selectedProfile]);

  const firstBar = useMemo(() => {
    const keys = Object.keys(categorical).slice(0, 1);
    if (!keys.length) return [];
    const attr = keys[0];
    return Object.entries(categorical[attr]).map(([name, v]) => ({
      name,
      score: Number(v.score ?? 0),
      confidence: Number(v.confidence ?? 0),
    }));
  }, [categorical]);

  const scorecardSwatches = ["bg-blue-600", "bg-violet-600", "bg-emerald-600", "bg-amber-600", "bg-rose-600"];

  const radarData = useMemo(() => {
    const cat = categorical as Record<string, Record<string, { score?: number }>>;
    return Object.keys(cat)
      .slice(0, 8)
      .map((k) => {
        const vals = Object.values(cat[k] ?? {});
        const best = vals.reduce((m, v) => Math.max(m, Number(v.score ?? 0)), 0);
        return { subject: k.slice(0, 12), A: best, fullMark: 1 };
      });
  }, [categorical]);

  if (!brandId) return <p>Select a brand.</p>;
  if (q.isLoading) return <div className="h-64 animate-pulse rounded bg-slate-200" />;
  if (q.isError) {
    return (
      <div className="rounded border border-warn/40 bg-amber-50 p-6 text-body">
        No profile computed yet. Run profile compute from API or upload ads and wait.
      </div>
    );
  }

  const recs = (selectedProfile?.recommendations ?? []) as Record<string, unknown>[];
  const era = q.data?.profile?.context?.current_era_hint?.title;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <h2 className="text-section">Creative profile</h2>
        {platforms.length > 0 && (
          <select
            className="rounded border px-2 py-1"
            value={platform || platforms[0]}
            onChange={(e) => setPlatform(e.target.value)}
          >
            {platforms.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        )}
        {era && <span className="text-datalabel text-muted">Era hint: {era}</span>}
      </div>

      <section className="rounded border bg-white p-4">
        <h3 className="text-cardtitle">Data health</h3>
        <pre className="mt-2 overflow-x-auto text-xs">{JSON.stringify(q.data?.data_health, null, 2)}</pre>
        <p className="mt-2 text-datalabel text-muted">
          Next profile update: scheduled via Celery Beat / Airflow (see ops runbook).
        </p>
      </section>

      {firstBar.length > 0 && (
        <section className="rounded border bg-white p-4">
          <h3 className="text-cardtitle">Sample categorical (first attribute)</h3>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={firstBar}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="score" fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {Object.keys(categorical).length > 0 && (
        <section className="rounded border bg-white p-4">
          <h3 className="text-cardtitle">Categorical scorecards</h3>
          <p className="mt-1 text-datalabel text-muted">
            Expand an attribute for value-level scores. Historical sparklines appear when the profile API includes
            per-attribute trends.
          </p>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {Object.entries(categorical).map(([attrKey, buckets], cardIdx) => (
              <details
                key={attrKey}
                className="rounded-lg border border-slate-200 bg-slate-50/40 p-3"
                data-testid={`profile-scorecard-${attrKey}`}
              >
                <summary className="cursor-pointer text-cardtitle">{attrKey}</summary>
                <div className="mt-3 space-y-2">
                  {Object.entries(buckets).map(([valueKey, v], i) => {
                    const score = Number(v.score ?? 0);
                    const sw = scorecardSwatches[(i + cardIdx) % scorecardSwatches.length];
                    return (
                      <div key={valueKey} className="flex items-center gap-2 text-datalabel">
                        <span
                          className={`h-3 w-3 shrink-0 rounded-sm ${sw}`}
                          data-testid="profile-scorecard-swatch"
                          aria-hidden
                        />
                        <span className="min-w-0 flex-1 truncate font-medium">{valueKey}</span>
                        <span className="tabular-nums text-muted">{(score * 100).toFixed(0)}%</span>
                        <span className="text-muted">n={v.n ?? "—"}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 overflow-x-auto rounded border bg-white">
                  <table className="w-full min-w-[280px] text-left text-datalabel">
                    <thead className="bg-slate-100 text-xs uppercase text-muted">
                      <tr>
                        <th className="px-2 py-1">Value</th>
                        <th className="px-2 py-1">Score</th>
                        <th className="px-2 py-1">Confidence</th>
                        <th className="px-2 py-1">n</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(buckets).map(([valueKey, v]) => (
                        <tr key={valueKey} className="border-t border-slate-100">
                          <td className="px-2 py-1">{valueKey}</td>
                          <td className="px-2 py-1 tabular-nums">{Number(v.score ?? 0).toFixed(3)}</td>
                          <td className="px-2 py-1 tabular-nums">{Number(v.confidence ?? 0).toFixed(2)}</td>
                          <td className="px-2 py-1 tabular-nums">{v.n ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            ))}
          </div>
        </section>
      )}

      {radarData.length > 0 && (
        <section className="rounded border bg-white p-4">
          <h3 className="text-cardtitle">Radar (top categorical axes)</h3>
          <div className="h-72">
            <ResponsiveContainer>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 9 }} />
                <PolarRadiusAxis angle={30} domain={[0, 1]} />
                <Radar name="Score" dataKey="A" stroke="#2563eb" fill="#2563eb" fillOpacity={0.35} />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <section className="rounded border bg-white p-4">
        <h3 className="text-cardtitle">Continuous attributes</h3>
        <ul className="space-y-2 text-datalabel">
          {Object.entries(
            (selectedProfile?.continuous ?? {}) as Record<string, Record<string, unknown>>,
          ).map(([k, v]) => {
            const nl = Boolean(v.is_non_linear ?? v.non_linear);
            return (
              <li key={k} className="rounded border border-slate-100 p-2">
                <span className="font-medium">{k}</span>
                {nl && (
                  <span className="ml-2 rounded bg-warn/20 px-2 py-0.5 text-xs text-warn">
                    Non-linear
                  </span>
                )}
                <pre className="mt-1 text-xs">{JSON.stringify(v)}</pre>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="rounded border bg-white p-4">
        <h3 className="text-cardtitle">Recommendations</h3>
        <ul className="space-y-2">
          {recs.slice(0, 5).map((r, i) => (
            <li key={i} className="text-body">
              <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(r, null, 2)}</pre>
              {String(r.type) === "ab_test_candidate" && (
                <Link className="text-datalabel text-accent" to="/tests/new">
                  Design A/B test
                </Link>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
