import { useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

type CompareRes = {
  ads: { ad_id: string; status: string; attributes: Record<string, unknown> }[];
  differences: Record<string, unknown[]>;
};

export function AdComparePage(): React.ReactElement {
  const { brandId } = useBrand();
  const [sp] = useSearchParams();
  const ids = sp.get("ids") ?? "";

  const q = useQuery({
    queryKey: ["compare", brandId, ids],
    queryFn: async () => {
      const { data } = await api.get<CompareRes>(`/api/v1/brands/${brandId}/ads/compare`, {
        params: { ad_ids: ids },
      });
      return data;
    },
    enabled: !!brandId && ids.split(",").filter(Boolean).length >= 2,
  });

  const chartData = useMemo(() => {
    if (!q.data) return [];
    return q.data.ads.map((a) => ({
      name: a.ad_id.slice(0, 8),
      attrs: Object.keys(a.attributes).length,
    }));
  }, [q.data]);

  if (!brandId) return <p>Select a brand.</p>;
  if (ids.split(",").filter(Boolean).length < 2) {
    return <p className="text-muted">Add ?ids=id1,id2 to URL (2–5 UUIDs).</p>;
  }

  return (
    <div className="space-y-4">
      <Link to="/ads" className="text-datalabel text-accent">
        ← Ads
      </Link>
      {q.isLoading ? (
        <div className="h-48 animate-pulse rounded bg-slate-200" />
      ) : q.isError ? (
        <p>Compare failed.</p>
      ) : (
        <>
          <h2 className="text-section">Compare {q.data?.ads.length} ads</h2>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={chartData}>
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="attrs" name="Attribute count" fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="rounded border bg-white p-4">
            <h3 className="text-cardtitle">Differing attributes</h3>
            <ul className="mt-2 max-h-96 overflow-auto text-datalabel">
              {Object.entries(q.data?.differences ?? {}).map(([k, vals]) => (
                <li key={k} className="border-b py-1">
                  <span className="font-medium">{k}</span>
                  <pre className="text-xs">{JSON.stringify(vals)}</pre>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
