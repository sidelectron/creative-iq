import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useBrand } from "../contexts/BrandContext";
import { api } from "../lib/api";

const steps = [
  { title: "Upload ads", body: "Use the Ads page to upload one or more videos." },
  { title: "Performance", body: "Add daily performance in each ad’s Performance tab or via CSV." },
  { title: "Guidelines", body: "Optional: upload brand guidelines in Settings." },
  { title: "Profile building", body: "Decomposition runs in the background; status updates below." },
];

type AdRow = { id: string; title: string | null; status: string };

export function OnboardingPage(): React.ReactElement {
  const [step, setStep] = useState(0);
  const { brandId } = useBrand();

  const adsQ = useQuery({
    queryKey: ["ads", brandId, "onboarding"],
    queryFn: async () => {
      const { data } = await api.get<{ items: AdRow[] }>(`/api/v1/brands/${brandId}/ads`, {
        params: { page: 1, page_size: 30 },
      });
      return data.items;
    },
    enabled: !!brandId,
    refetchInterval: (q) => {
      const rows = q.state.data ?? [];
      const pending = rows.some((a) => a.status === "ingested" || a.status === "decomposing");
      return pending ? 4000 : false;
    },
  });

  const statusLine = useMemo(() => {
    const rows = adsQ.data ?? [];
    if (rows.length === 0) return "No ads uploaded yet.";
    const counts = rows.reduce(
      (acc, a) => {
        acc[a.status] = (acc[a.status] ?? 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );
    return Object.entries(counts)
      .map(([k, v]) => `${k}: ${v}`)
      .join(" · ");
  }, [adsQ.data]);

  return (
    <div className="mx-auto max-w-xl">
      <h2 className="text-section">Onboarding</h2>
      {brandId && (
        <p className="mt-2 rounded border border-slate-200 bg-white p-3 text-datalabel text-muted">
          Decomposition status (polling): <span className="text-slate-800">{statusLine}</span>
        </p>
      )}
      <ol className="mt-6 space-y-4">
        {steps.map((s, i) => (
          <li
            key={s.title}
            className={`rounded-lg border p-4 ${
              i === step ? "border-accent bg-accent/5" : "border-slate-200 bg-white"
            }`}
          >
            <p className="text-cardtitle">
              Step {i + 1}: {s.title}
            </p>
            <p className="mt-1 text-body text-muted">{s.body}</p>
          </li>
        ))}
      </ol>
      <div className="mt-6 flex gap-2">
        <button
          type="button"
          className="rounded border px-4 py-2"
          disabled={step === 0}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
        >
          Back
        </button>
        <button
          type="button"
          className="rounded bg-accent px-4 py-2 text-white"
          onClick={() => setStep((s) => Math.min(steps.length - 1, s + 1))}
        >
          {step === steps.length - 1 ? "Done" : "Next"}
        </button>
      </div>
      {brandId && (
        <p className="mt-4 text-datalabel">
          <Link className="text-accent hover:underline" to="/ads">
            Go to Ads
          </Link>
        </p>
      )}
    </div>
  );
}
