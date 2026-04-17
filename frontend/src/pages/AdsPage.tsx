import { useCallback, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";
import { fingerprintSearchBlob } from "../lib/adFingerprintSearch";

type AdRow = {
  id: string;
  title: string | null;
  platform: string;
  status: string;
  created_at: string;
  signed_video_url: string | null;
  performance_summary?: { total_impressions?: number; total_clicks?: number; average_ctr?: number | null };
  fingerprint_attributes?: Record<string, unknown> | null;
};

type Paginated<T> = { items: T[]; total: number; page: number; page_size: number };

const platforms = ["meta", "tiktok", "youtube", "instagram"];

export function AdsPage(): React.ReactElement {
  const { brandId } = useBrand();
  const qc = useQueryClient();
  const [sp, setSp] = useSearchParams();
  const titleQ = sp.get("q") ?? "";
  const fpq = sp.get("fpq") ?? "";
  const [platform, setPlatform] = useState<string>("");
  const [sort, setSort] = useState("newest");
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const listQ = useQuery({
    queryKey: ["ads", brandId, platform, sort],
    queryFn: async () => {
      const { data } = await api.get<Paginated<AdRow>>(`/api/v1/brands/${brandId}/ads`, {
        params: {
          page: 1,
          page_size: 50,
          platform: platform || undefined,
          include_fingerprint: true,
        },
      });
      return data;
    },
    enabled: !!brandId,
  });

  const filtered = useMemo(() => {
    let rows = listQ.data?.items ?? [];
    if (titleQ.trim()) {
      const t = titleQ.toLowerCase();
      rows = rows.filter((r) => (r.title ?? "").toLowerCase().includes(t));
    }
    if (fpq.trim()) {
      const needle = fpq.toLowerCase();
      rows = rows.filter((r) => fingerprintSearchBlob(r.fingerprint_attributes ?? null).includes(needle));
    }
    if (sort === "best_ctr") {
      rows = [...rows].sort(
        (a, b) =>
          (b.performance_summary?.average_ctr ?? 0) - (a.performance_summary?.average_ctr ?? 0),
      );
    } else if (sort === "most_impressions") {
      rows = [...rows].sort(
        (a, b) =>
          (b.performance_summary?.total_impressions ?? 0) -
          (a.performance_summary?.total_impressions ?? 0),
      );
    }
    return rows;
  }, [listQ.data, titleQ, fpq, sort]);

  const uploadM = useMutation({
    mutationFn: async (files: FileList) => {
      for (const file of Array.from(files)) {
        const fd = new FormData();
        fd.append("video", file);
        fd.append("platform", platform || "meta");
        fd.append("title", file.name.replace(/\.[^.]+$/, ""));
        await api.post(`/api/v1/brands/${brandId}/ads/upload`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      }
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["ads", brandId], exact: false }),
  });

  const onFiles = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files?.length) uploadM.mutate(e.target.files);
    },
    [uploadM],
  );

  if (!brandId) return <p className="text-muted">Select a brand.</p>;

  return (
    <div className="space-y-4">
      <div
        className={`rounded-lg border-2 border-dashed p-6 text-center text-datalabel transition-colors ${
          dragOver ? "border-accent bg-accent/5" : "border-slate-300 bg-white"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files?.length) uploadM.mutate(e.dataTransfer.files);
        }}
      >
        <p>Drag and drop video files here, or use Upload.</p>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="text-datalabel text-muted">Platform filter</label>
          <select
            className="mt-1 block rounded border px-2 py-1"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
          >
            <option value="">All</option>
            {platforms.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-datalabel text-muted">Sort</label>
          <select
            className="mt-1 block rounded border px-2 py-1"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="newest">Newest</option>
            <option value="best_ctr">Best CTR</option>
            <option value="most_impressions">Most impressions</option>
          </select>
        </div>
        <div className="flex-1">
          <label className="text-datalabel text-muted">Title search</label>
          <input
            className="mt-1 w-full max-w-xs rounded border px-2 py-1"
            value={titleQ}
            onChange={(e) => {
              const v = e.target.value;
              const next = new URLSearchParams(sp);
              if (v) next.set("q", v);
              else next.delete("q");
              setSp(next);
            }}
            placeholder="Filter client-side…"
          />
        </div>
        <div className="flex-1">
          <label className="text-datalabel text-muted">Fingerprint contains</label>
          <input
            className="mt-1 w-full max-w-xs rounded border px-2 py-1"
            value={fpq}
            onChange={(e) => {
              const v = e.target.value;
              const next = new URLSearchParams(sp);
              if (v) next.set("fpq", v);
              else next.delete("fpq");
              setSp(next);
            }}
            placeholder="e.g. hook, emotional_tone value…"
          />
        </div>
        <div>
          <input ref={fileRef} type="file" accept="video/*" multiple className="hidden" onChange={onFiles} />
          <button
            type="button"
            className="rounded bg-accent px-4 py-2 text-white"
            onClick={() => fileRef.current?.click()}
            disabled={uploadM.isPending}
          >
            {uploadM.isPending ? "Uploading…" : "Upload videos"}
          </button>
        </div>
      </div>

      {listQ.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-40 animate-pulse rounded-lg bg-slate-200" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-body text-muted">
          {(listQ.data?.items?.length ?? 0) > 0
            ? "No ads match the current title or fingerprint filters."
            : "No ads yet — upload your first ad to get started."}
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((ad) => (
            <li key={ad.id} className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
              <Link to={`/ads/${ad.id}`} className="block">
                <div className="aspect-video overflow-hidden rounded bg-slate-100">
                  {ad.signed_video_url ? (
                    <video src={ad.signed_video_url} className="h-full w-full object-cover" muted />
                  ) : (
                    <div className="flex h-full items-center justify-center text-datalabel text-muted">
                      No preview
                    </div>
                  )}
                </div>
                <p className="mt-2 text-cardtitle line-clamp-1">{ad.title ?? "Untitled"}</p>
                <p className="flex items-center gap-2 text-datalabel text-muted">
                  {ad.platform} · {ad.status}
                  {(ad.status === "decomposing" || ad.status === "ingested") && (
                    <Loader2 className="h-4 w-4 animate-spin text-accent" aria-label="Processing" />
                  )}
                </p>
                {ad.performance_summary && (
                  <p className="text-datalabel">
                    CTR:{" "}
                    {ad.performance_summary.average_ctr != null
                      ? (ad.performance_summary.average_ctr * 100).toFixed(2) + "%"
                      : "—"}{" "}
                    · imp: {ad.performance_summary.total_impressions ?? 0}
                  </p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}

      {filtered.length >= 2 && (
        <p className="text-datalabel">
          <Link
            className="text-accent hover:underline"
            to={`/ads/compare?ids=${filtered
              .slice(0, 5)
              .map((a) => a.id)
              .join(",")}`}
          >
            Compare up to 5 on this page
          </Link>
        </p>
      )}
    </div>
  );
}
