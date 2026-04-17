import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

type ABRow = {
  id: string;
  attribute_tested: string;
  status: string;
  target_metric: string;
  hypothesis: string | null;
  results: Record<string, unknown> | null;
};

type Paginated<T> = { items: T[] };

const cols = [
  { id: "proposed", title: "Proposed" },
  { id: "active", title: "Active" },
  { id: "completed", title: "Completed" },
] as const;

export function ABTestsPage(): React.ReactElement {
  const { brandId } = useBrand();
  const qc = useQueryClient();
  const [dragId, setDragId] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["ab-tests", brandId],
    queryFn: async () => {
      const { data } = await api.get<Paginated<ABRow>>(`/api/v1/brands/${brandId}/tests`, {
        params: { page: 1, page_size: 100 },
      });
      return data.items;
    },
    enabled: !!brandId,
  });

  const grouped = useMemo(() => {
    const g: Record<string, ABRow[]> = { proposed: [], active: [], completed: [] };
    (q.data ?? []).forEach((t) => {
      if (t.status === "cancelled") return;
      if (g[t.status]) g[t.status].push(t);
    });
    return g;
  }, [q.data]);

  const totalVisible = useMemo(
    () => cols.reduce((n, c) => n + (grouped[c.id]?.length ?? 0), 0),
    [grouped],
  );

  const patchM = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: string }) => {
      await api.patch(`/api/v1/brands/${brandId}/tests/${id}`, {
        status,
        platform: "meta",
      });
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["ab-tests", brandId] }),
  });

  if (!brandId) return <p>Select a brand.</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Link to="/tests/new" className="rounded bg-accent px-4 py-2 text-white">
          New test wizard
        </Link>
        <Link to="/tests/recommendations" className="rounded border px-4 py-2">
          Recommendations
        </Link>
      </div>
      {q.isLoading ? (
        <div className="grid grid-cols-3 gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-40 animate-pulse rounded bg-slate-200" />
          ))}
        </div>
      ) : totalVisible === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-body text-muted">
          No A/B tests yet — the system recommends testing hook types based on your profile. Open{" "}
          <Link className="text-accent underline" to="/tests/recommendations">
            Recommendations
          </Link>{" "}
          or create a test.
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-3">
          {cols.map((col) => (
            <div
              key={col.id}
              className="min-h-[200px] rounded-lg border border-slate-200 bg-slate-50 p-2"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const id = e.dataTransfer.getData("text/ab-id");
                const from = e.dataTransfer.getData("text/from-status");
                if (!id || from === col.id) return;
                if (col.id === "completed" && from !== "active") return;
                if (col.id === "active" && from !== "proposed") return;
                patchM.mutate({ id, status: col.id });
              }}
            >
              <h3 className="border-b border-slate-200 px-2 py-1 text-cardtitle">{col.title}</h3>
              <ul className="space-y-2 p-2">
                {grouped[col.id]?.map((t) => (
                  <li key={t.id}>
                    <div
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.setData("text/ab-id", t.id);
                        e.dataTransfer.setData("text/from-status", t.status);
                        setDragId(t.id);
                      }}
                      onDragEnd={() => setDragId(null)}
                      className={`rounded border bg-white p-2 text-datalabel ${
                        dragId === t.id ? "opacity-50" : ""
                      }`}
                    >
                      <Link to={`/tests/${t.id}`} className="font-medium text-accent">
                        {t.attribute_tested}
                      </Link>
                      <p className="text-muted">{t.target_metric}</p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {t.status === "proposed" && (
                          <>
                            <button
                              type="button"
                              className="rounded border px-2 py-0.5"
                              onClick={() => patchM.mutate({ id: t.id, status: "active" })}
                            >
                              Start
                            </button>
                            <button
                              type="button"
                              className="rounded border px-2 py-0.5 text-danger"
                              onClick={() => patchM.mutate({ id: t.id, status: "cancelled" })}
                            >
                              Cancel
                            </button>
                          </>
                        )}
                        {t.status === "active" && (
                          <>
                            <button
                              type="button"
                              className="rounded border px-2 py-0.5"
                              onClick={() => patchM.mutate({ id: t.id, status: "completed" })}
                            >
                              Complete
                            </button>
                            <button
                              type="button"
                              className="rounded border px-2 py-0.5 text-danger"
                              onClick={() => patchM.mutate({ id: t.id, status: "cancelled" })}
                            >
                              Cancel
                            </button>
                          </>
                        )}
                        {t.status === "completed" && t.results && (
                          <span className="text-success">Has results</span>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      <p className="text-datalabel text-muted">
        Drag cards between columns for valid transitions, or use action buttons (API PATCH).
      </p>
    </div>
  );
}
