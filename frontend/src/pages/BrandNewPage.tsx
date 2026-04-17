import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

type Preset = { industry: string; platform: string; description: string | null };

export function BrandNewPage(): React.ReactElement {
  const qc = useQueryClient();
  const nav = useNavigate();
  const { setBrandId } = useBrand();
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [description, setDescription] = useState("");
  const [website, setWebsite] = useState("");
  const [metrics, setMetrics] = useState<string[]>(["ctr"]);

  const presetsQ = useQuery({
    queryKey: ["presets"],
    queryFn: async () => {
      const { data } = await api.get<Preset[]>("/api/v1/presets");
      return data;
    },
  });

  const industries = useMemo(() => {
    const s = new Set<string>();
    (presetsQ.data ?? []).forEach((p) => s.add(p.industry));
    return [...s].sort();
  }, [presetsQ.data]);

  const createM = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ id: string }>("/api/v1/brands", {
        name,
        industry: industry || null,
        description: description || null,
        website_url: website || null,
        success_metrics: metrics,
      });
      return data;
    },
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["brands"] });
      setBrandId(data.id);
      nav("/onboarding");
    },
  });

  const toggleMetric = (m: string) => {
    setMetrics((prev) =>
      prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m],
    );
  };

  const [dragMetricIdx, setDragMetricIdx] = useState<number | null>(null);

  const reorderMetric = (from: number, to: number) => {
    if (from === to || from < 0 || to < 0) return;
    setMetrics((prev) => {
      const next = [...prev];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
  };

  const allMetrics = ["ctr", "cpa", "roas", "completion_rate"];

  return (
    <div className="mx-auto max-w-lg rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="text-section">New brand</h2>
      <form
        className="mt-4 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          createM.mutate();
        }}
      >
        <div>
          <label className="text-datalabel text-muted">Name *</label>
          <input
            required
            className="mt-1 w-full rounded border px-3 py-2"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label className="text-datalabel text-muted">Industry</label>
          <select
            className="mt-1 w-full rounded border px-3 py-2"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          >
            <option value="">Select…</option>
            {industries.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-datalabel text-muted">Description</label>
          <textarea
            className="mt-1 w-full rounded border px-3 py-2"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div>
          <label className="text-datalabel text-muted">Website</label>
          <input
            className="mt-1 w-full rounded border px-3 py-2"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
          />
        </div>
        <div>
          <p className="text-datalabel text-muted">Success metrics (toggle + drag rows to rank)</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {allMetrics.map((m) => (
              <button
                key={m}
                type="button"
                className={`rounded-full border px-3 py-1 text-datalabel uppercase ${
                  metrics.includes(m) ? "border-accent bg-accent/10" : "border-slate-200"
                }`}
                onClick={() => toggleMetric(m)}
              >
                {m}
              </button>
            ))}
          </div>
          <ol className="mt-3 space-y-1 rounded border border-slate-200 bg-slate-50 p-2">
            {metrics.map((m, i) => (
              <li
                key={m}
                draggable
                onDragStart={() => setDragMetricIdx(i)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => {
                  if (dragMetricIdx !== null) reorderMetric(dragMetricIdx, i);
                  setDragMetricIdx(null);
                }}
                className="cursor-grab rounded border border-white bg-white px-3 py-2 text-datalabel active:cursor-grabbing"
              >
                {i + 1}. {m}{" "}
                <span className="text-muted">(drag to reorder)</span>
              </li>
            ))}
          </ol>
        </div>
        {createM.isError && (
          <p className="text-datalabel text-danger">Could not create brand.</p>
        )}
        <button
          type="submit"
          disabled={createM.isPending}
          className="w-full rounded bg-accent py-2 text-white disabled:opacity-60"
        >
          {createM.isPending ? "Creating…" : "Create brand"}
        </button>
      </form>
    </div>
  );
}
