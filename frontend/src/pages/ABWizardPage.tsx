import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

const steps = ["Attribute", "Variants", "Metric", "Review", "Confirm"];

export type ABWizardLocationState = {
  fromRecommendation?: {
    attribute?: string;
    hypothesis?: string;
    target_metric?: string;
  };
};

type DesignPreview = {
  sample_size_per_variant: number;
  estimated_budget_per_variant: number | null;
  estimated_duration_days: number | null;
  hypothesis: string;
  alpha: number;
  power: number;
  mde_relative: number;
  mde_absolute: number;
};

export function ABWizardPage(): React.ReactElement {
  const { brandId } = useBrand();
  const nav = useNavigate();
  const location = useLocation();
  const [step, setStep] = useState(0);
  const [attribute, setAttribute] = useState("hook_type");
  const [v1, setV1] = useState("A");
  const [v2, setV2] = useState("B");
  const [targetMetric, setTargetMetric] = useState("ctr");
  const [hypothesis, setHypothesis] = useState("");
  const [baseline, setBaseline] = useState("0.02");
  const [avgCpm, setAvgCpm] = useState("12");
  const [avgDailyImpressions, setAvgDailyImpressions] = useState("5000");

  useEffect(() => {
    const st = location.state as ABWizardLocationState | null;
    const fr = st?.fromRecommendation;
    if (!fr) return;
    if (fr.attribute) setAttribute(fr.attribute);
    if (fr.hypothesis) setHypothesis(fr.hypothesis);
    if (fr.target_metric) setTargetMetric(fr.target_metric);
    nav(location.pathname + location.search, { replace: true, state: {} });
  }, [location.pathname, location.search, location.state, nav]);

  const previewBody = useMemo(
    () => ({
      attribute_to_test: attribute,
      variants: [v1, v2],
      target_metric: targetMetric,
      hypothesis: hypothesis.trim() || null,
      baseline_metric: Number(baseline) || 0.02,
      avg_cpm: Number(avgCpm) || null,
      avg_daily_impressions: Number(avgDailyImpressions) || null,
    }),
    [attribute, v1, v2, targetMetric, hypothesis, baseline, avgCpm, avgDailyImpressions],
  );

  const previewQ = useQuery({
    queryKey: ["ab-preview", brandId, previewBody],
    queryFn: async () => {
      const { data } = await api.post<DesignPreview>(
        `/api/v1/brands/${brandId}/tests/preview-design`,
        previewBody,
      );
      return data;
    },
    enabled: !!brandId && step >= 3,
    retry: false,
  });

  const createM = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ id: string }>(`/api/v1/brands/${brandId}/tests`, {
        attribute_to_test: attribute,
        variants: [v1, v2],
        target_metric: targetMetric,
        hypothesis: hypothesis || null,
        baseline_metric: Number(baseline) || undefined,
        avg_cpm: Number(avgCpm) || undefined,
        avg_daily_impressions: Number(avgDailyImpressions) || undefined,
      });
      return data;
    },
    onSuccess: (d) => nav("/tests/" + d.id),
  });

  if (!brandId) return <p>Select a brand.</p>;

  const pv = previewQ.data;

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <Link to="/tests" className="text-datalabel text-accent">
        ← Tests
      </Link>
      <h2 className="text-section">Design A/B test</h2>
      <p className="text-datalabel text-muted">
        Step {step + 1} / {steps.length}: {steps[step]}
      </p>
      {step === 0 && (
        <input
          className="w-full rounded border px-3 py-2"
          value={attribute}
          onChange={(e) => setAttribute(e.target.value)}
          placeholder="Attribute to test"
        />
      )}
      {step === 1 && (
        <div className="space-y-2">
          <input
            className="w-full rounded border px-3 py-2"
            value={v1}
            onChange={(e) => setV1(e.target.value)}
            placeholder="Variant 1 label"
          />
          <input
            className="w-full rounded border px-3 py-2"
            value={v2}
            onChange={(e) => setV2(e.target.value)}
            placeholder="Variant 2 label"
          />
        </div>
      )}
      {step === 2 && (
        <select
          className="w-full rounded border px-3 py-2"
          value={targetMetric}
          onChange={(e) => setTargetMetric(e.target.value)}
        >
          <option value="ctr">CTR</option>
          <option value="cpa">CPA</option>
          <option value="roas">ROAS</option>
        </select>
      )}
      {step === 3 && (
        <div className="space-y-2">
          <textarea
            className="w-full rounded border px-3 py-2"
            rows={3}
            value={hypothesis}
            onChange={(e) => setHypothesis(e.target.value)}
            placeholder="Hypothesis"
          />
          <label className="text-datalabel text-muted">Baseline metric</label>
          <input
            className="w-full rounded border px-3 py-2"
            value={baseline}
            onChange={(e) => setBaseline(e.target.value)}
          />
          <label className="text-datalabel text-muted">Assumed CPM (USD, optional)</label>
          <input
            className="w-full rounded border px-3 py-2"
            value={avgCpm}
            onChange={(e) => setAvgCpm(e.target.value)}
            inputMode="decimal"
          />
          <label className="text-datalabel text-muted">Avg daily impressions (optional)</label>
          <input
            className="w-full rounded border px-3 py-2"
            value={avgDailyImpressions}
            onChange={(e) => setAvgDailyImpressions(e.target.value)}
            inputMode="numeric"
          />
          <p className="text-datalabel text-muted">
            Estimates use the same designer as create; set CPM + impressions for budget and duration.
          </p>
          {previewQ.isFetching && <p className="text-datalabel text-muted">Computing preview…</p>}
          {previewQ.isError && (
            <p className="text-datalabel text-danger">Preview unavailable (API offline or validation error).</p>
          )}
          {pv && (
            <div className="rounded border border-slate-200 bg-slate-50 p-3 text-datalabel" data-testid="ab-design-preview">
              <p>
                <strong>Sample size / variant:</strong> {pv.sample_size_per_variant.toLocaleString()}
              </p>
              <p>
                <strong>Est. budget / variant:</strong>{" "}
                {pv.estimated_budget_per_variant != null
                  ? `$${pv.estimated_budget_per_variant.toFixed(2)}`
                  : "— (add CPM)"}
              </p>
              <p>
                <strong>Est. duration:</strong>{" "}
                {pv.estimated_duration_days != null ? `${pv.estimated_duration_days} days` : "— (add daily imps)"}
              </p>
              <p className="text-muted">
                MDE {Math.round(pv.mde_relative * 100)}% · α={pv.alpha} · power={pv.power}
              </p>
            </div>
          )}
        </div>
      )}
      {step === 4 && (
        <div className="rounded border bg-slate-50 p-4 text-datalabel">
          <p>Attribute: {attribute}</p>
          <p>
            Variants: {v1}, {v2}
          </p>
          <p>Metric: {targetMetric}</p>
          <p>Hypothesis: {hypothesis || "—"}</p>
          {pv && (
            <div className="mt-3 border-t border-slate-200 pt-3" data-testid="ab-design-preview-confirm">
              <p>
                <strong>Sample size / variant:</strong> {pv.sample_size_per_variant.toLocaleString()}
              </p>
              <p>
                <strong>Est. budget / variant:</strong>{" "}
                {pv.estimated_budget_per_variant != null
                  ? `$${pv.estimated_budget_per_variant.toFixed(2)}`
                  : "—"}
              </p>
              <p>
                <strong>Est. duration:</strong>{" "}
                {pv.estimated_duration_days != null ? `${pv.estimated_duration_days} days` : "—"}
              </p>
            </div>
          )}
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          className="rounded border px-4 py-2"
          disabled={step === 0}
          onClick={() => setStep((s) => s - 1)}
        >
          Back
        </button>
        {step < 4 ? (
          <button
            type="button"
            className="rounded bg-accent px-4 py-2 text-white"
            onClick={() => setStep((s) => s + 1)}
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            className="rounded bg-accent px-4 py-2 text-white"
            disabled={createM.isPending}
            onClick={() => createM.mutate()}
          >
            {createM.isPending ? "Creating…" : "Confirm"}
          </button>
        )}
      </div>
    </div>
  );
}
