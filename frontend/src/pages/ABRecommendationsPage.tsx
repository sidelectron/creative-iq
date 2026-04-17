import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

export function ABRecommendationsPage(): React.ReactElement {
  const { brandId } = useBrand();
  const q = useQuery({
    queryKey: ["ab-recs", brandId],
    queryFn: async () => {
      const { data } = await api.get<{ recommendations: Record<string, unknown>[] }>(
        `/api/v1/brands/${brandId}/tests/recommendations`,
      );
      return data.recommendations;
    },
    enabled: !!brandId,
    retry: false,
  });

  if (!brandId) return <p>Select a brand.</p>;

  return (
    <div className="space-y-4">
      <Link to="/tests" className="text-datalabel text-accent">
        ← Tests
      </Link>
      <h2 className="text-section">Test recommendations</h2>
      {q.isLoading && <div className="h-32 animate-pulse rounded bg-slate-200" />}
      {q.isError && <p className="text-muted">No recommendations (profile may be missing).</p>}
      <ul className="space-y-3">
        {(q.data ?? []).map((r, i) => {
          const rec = r as Record<string, unknown>;
          const attribute = typeof rec.attribute === "string" ? rec.attribute : undefined;
          const message = typeof rec.message === "string" ? rec.message : undefined;
          return (
            <li key={i} className="rounded border bg-white p-4">
              <pre className="text-xs">{JSON.stringify(r, null, 2)}</pre>
              <Link
                to="/tests/new"
                state={{
                  fromRecommendation: {
                    attribute: attribute ?? "hook_type",
                    hypothesis: message ?? "",
                    target_metric: "ctr",
                  },
                }}
                className="mt-2 inline-block text-datalabel text-accent"
              >
                Create this test
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
