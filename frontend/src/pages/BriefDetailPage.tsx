import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

type Variant = {
  display_label?: string;
  name?: string;
  attribute_specs?: Record<string, unknown>;
  storyboard?: { scenes?: unknown[] };
  compliance?: unknown;
};

type JobStatus = {
  id: string;
  status: string;
  pipeline_stage: string | null;
  result: { variants?: Variant[] } | null;
  error: string | null;
};

export function BriefDetailPage(): React.ReactElement {
  const { jobId } = useParams<{ jobId: string }>();
  const { brandId } = useBrand();
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);
  const [rating, setRating] = useState<number>(4);
  const [ratingMode, setRatingMode] = useState<"stars" | "thumbs_up" | "thumbs_down">("stars");
  const [fbText, setFbText] = useState("");

  const q = useQuery({
    queryKey: ["gen-job", brandId, jobId],
    queryFn: async () => {
      const { data } = await api.get<JobStatus>(`/api/v1/brands/${brandId}/generate/${jobId}`);
      return data;
    },
    enabled: !!brandId && !!jobId,
    refetchInterval: (query) =>
      query.state.data?.status === "completed" || query.state.data?.status === "failed"
        ? false
        : 4000,
  });

  const variants = q.data?.result?.variants ?? [];
  const labels = useMemo(
    () =>
      variants.map((v, i) => String(v.display_label ?? v.name ?? `Variant ${i + 1}`)),
    [variants],
  );

  useEffect(() => {
    if (tab >= labels.length) setTab(0);
  }, [labels.length, tab]);

  const exportFmt = async (format: string, suffix = "") => {
    const res = await api.get(`/api/v1/brands/${brandId}/generate/${jobId}/export`, {
      params: { format },
      responseType: "blob",
    });
    const blob = res.data as Blob;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const ext = format === "markdown" ? "md" : format;
    a.download = `brief-${jobId}${suffix ? `-${suffix}` : ""}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportAllFormats = async () => {
    for (const fmt of ["json", "markdown", "pdf"] as const) {
      await exportFmt(fmt, "all");
      await new Promise((r) => setTimeout(r, 400));
    }
  };

  const fbM = useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/brands/${brandId}/generate/${jobId}/feedback`, {
        variant_index: tab,
        rating: ratingMode === "stars" ? rating : ratingMode === "thumbs_up" ? "thumbs_up" : "thumbs_down",
        feedback: fbText,
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["gen-job", brandId, jobId] });
      setFbText("");
    },
  });

  if (!brandId || !jobId) return <p>Missing job.</p>;

  const v = variants[tab];

  return (
    <div className="space-y-4">
      <Link to="/briefs" className="text-datalabel text-accent">
        ← Briefs
      </Link>
      {q.isLoading ? (
        <div className="h-40 animate-pulse rounded bg-slate-200" />
      ) : !q.data ? (
        <p>Not found</p>
      ) : (
        <>
          <h2 className="text-section">Job {q.data.status}</h2>
          {q.data.error && <p className="text-danger">{q.data.error}</p>}
          {labels.length > 0 && (
            <div className="flex flex-wrap gap-2 border-b pb-2">
              {labels.map((l, i) => (
                <button
                  key={l}
                  type="button"
                  className={`rounded-full border px-3 py-1 text-datalabel ${
                    tab === i ? "border-accent bg-accent/10" : ""
                  }`}
                  onClick={() => setTab(i)}
                >
                  {l}
                </button>
              ))}
            </div>
          )}
          {v && (
            <div className="rounded border bg-white p-4">
              <h3 className="text-cardtitle">Attributes</h3>
              <pre className="mt-2 max-h-64 overflow-auto text-xs">
                {JSON.stringify(v.attribute_specs ?? {}, null, 2)}
              </pre>
              {v.storyboard?.scenes && (
                <div className="mt-4">
                  <h4 className="text-section">Storyboard</h4>
                  <div className="mt-2 flex gap-2 overflow-x-auto">
                    {(v.storyboard.scenes as Record<string, unknown>[]).map((s, i) => (
                      <div key={i} className="min-w-[140px] shrink-0 rounded border p-2 text-xs">
                        {JSON.stringify(s)}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded border px-3 py-1"
              onClick={() => void exportFmt("json")}
            >
              Export JSON
            </button>
            <button
              type="button"
              className="rounded border px-3 py-1"
              onClick={() => void exportFmt("markdown")}
            >
              Export Markdown
            </button>
            <button
              type="button"
              className="rounded border px-3 py-1"
              onClick={() => void exportFmt("pdf")}
            >
              Export PDF
            </button>
            <button
              type="button"
              className="rounded border border-accent px-3 py-1 text-datalabel text-accent"
              onClick={() => void exportAllFormats()}
            >
              Export all formats (batch)
            </button>
          </div>
          <div className="rounded border bg-slate-50 p-4">
            <h3 className="text-cardtitle">Feedback</h3>
            <label className="mt-2 block text-datalabel text-muted">Rating</label>
            <select
              className="mt-1 rounded border px-2 py-1"
              value={ratingMode}
              onChange={(e) => setRatingMode(e.target.value as typeof ratingMode)}
            >
              <option value="stars">Stars (1–5)</option>
              <option value="thumbs_up">Thumbs up</option>
              <option value="thumbs_down">Thumbs down</option>
            </select>
            {ratingMode === "stars" && (
              <label className="mt-2 block text-datalabel">
                Level
                <input
                  type="range"
                  min={1}
                  max={5}
                  value={rating}
                  onChange={(e) => setRating(Number(e.target.value))}
                  className="ml-2"
                />
                <span className="ml-2">{rating}</span>
              </label>
            )}
            <textarea
              className="mt-2 w-full rounded border px-2 py-1"
              rows={2}
              placeholder="Optional comment"
              value={fbText}
              onChange={(e) => setFbText(e.target.value)}
            />
            <button
              type="button"
              className="mt-2 rounded bg-accent px-4 py-2 text-white"
              disabled={fbM.isPending}
              onClick={() => fbM.mutate()}
            >
              Submit feedback
            </button>
          </div>
        </>
      )}
    </div>
  );
}
