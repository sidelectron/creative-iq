import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

type ABRow = {
  id: string;
  attribute_tested: string;
  status: string;
  target_metric: string;
  hypothesis: string | null;
  variants: unknown[];
  results: Record<string, unknown> | null;
  sample_size_required: number | null;
  estimated_budget: string | null;
};

export function ABTestDetailPage(): React.ReactElement {
  const { testId } = useParams<{ testId: string }>();
  const { brandId } = useBrand();

  const q = useQuery({
    queryKey: ["ab-test", brandId, testId],
    queryFn: async () => {
      const { data } = await api.get<ABRow>(`/api/v1/brands/${brandId}/tests/${testId}`);
      return data;
    },
    enabled: !!brandId && !!testId,
  });

  if (!brandId || !testId) return <p>Missing.</p>;
  if (q.isLoading) return <div className="h-40 animate-pulse rounded bg-slate-200" />;
  if (!q.data) return <p>Not found.</p>;
  const t = q.data;
  const res = t.results;

  return (
    <div className="space-y-4">
      <Link to="/tests" className="text-datalabel text-accent">
        ← Tests
      </Link>
      <h2 className="text-section">{t.attribute_tested}</h2>
      <p className="text-body text-muted">
        {t.status} · target {t.target_metric}
      </p>
      {t.hypothesis && <p className="text-body">{t.hypothesis}</p>}
      <section className="rounded border bg-white p-4">
        <h3 className="text-cardtitle">Plan</h3>
        <p className="text-datalabel">Sample size: {t.sample_size_required ?? "—"}</p>
        <p className="text-datalabel">Budget est.: {t.estimated_budget ?? "—"}</p>
        <pre className="mt-2 overflow-x-auto text-xs">{JSON.stringify(t.variants, null, 2)}</pre>
      </section>
      {res && (
        <section className="rounded border bg-white p-4">
          <h3 className="text-cardtitle">Results</h3>
          <p className="text-datalabel">
            Winner: <strong>{String(res.winner ?? res.winning_variant ?? "—")}</strong>
          </p>
          <p className="text-datalabel">
            Confidence / CI:{" "}
            {JSON.stringify(res.confidence_interval ?? res.ci ?? res.confidence ?? "—")}
          </p>
          <p className="text-datalabel">Effect size: {String(res.effect_size ?? "—")}</p>
          <p className="text-datalabel">p-value / Bayesian notes in payload:</p>
          <pre className="mt-2 max-h-96 overflow-auto text-xs">{JSON.stringify(res, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}
