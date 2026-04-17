import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";
import { format } from "date-fns";

type JobRow = {
  id: string;
  campaign_description: string;
  num_variants: number;
  created_at: string;
  primary_summary: string;
  chip_hook?: string | null;
  chip_duration?: string | null;
  chip_tone?: string | null;
};

type Paginated<T> = { items: T[] };

export function BriefsPage(): React.ReactElement {
  const { brandId } = useBrand();
  const q = useQuery({
    queryKey: ["briefs", brandId],
    queryFn: async () => {
      const { data } = await api.get<Paginated<JobRow>>(
        `/api/v1/brands/${brandId}/generate/history`,
        { params: { page: 1, page_size: 50 } },
      );
      return data.items;
    },
    enabled: !!brandId,
  });

  if (!brandId) return <p>Select a brand.</p>;

  return (
    <div className="space-y-4">
      <h2 className="text-section">Briefs & generation</h2>
      {q.isLoading ? (
        <div className="h-40 animate-pulse rounded bg-slate-200" />
      ) : (q.data ?? []).length === 0 ? (
        <p className="rounded border border-dashed p-8 text-center text-muted">
          No generation jobs yet.
        </p>
      ) : (
        <ul className="space-y-3">
          {q.data?.map((j) => (
            <li key={j.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <Link to={`/briefs/${j.id}`} className="text-cardtitle text-accent hover:underline">
                {j.campaign_description || "Campaign"}
              </Link>
              <p className="text-datalabel text-muted">
                {format(new Date(j.created_at), "PP")} · {j.num_variants} variants
              </p>
              <p className="mt-1 line-clamp-2 text-body">{j.primary_summary}</p>
              <div className="mt-2 flex flex-wrap gap-2 text-datalabel">
                <span className="rounded-full bg-slate-100 px-2 py-0.5">variants: {j.num_variants}</span>
                {j.chip_hook && (
                  <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-indigo-900">hook: {j.chip_hook}</span>
                )}
                {j.chip_duration && (
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-amber-900">
                    duration: {j.chip_duration}
                  </span>
                )}
                {j.chip_tone && (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-900">tone: {j.chip_tone}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
