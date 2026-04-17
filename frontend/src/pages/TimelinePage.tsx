import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Rocket,
  Shuffle,
  Building2,
  Swords,
  StickyNote,
  AlertTriangle,
  CircleDot,
} from "lucide-react";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";
import { format } from "date-fns";

type Item = {
  timestamp: string;
  event_type: string;
  title: string;
  description: string | null;
  source: string;
  impact: Record<string, unknown>;
  related_data: Record<string, unknown>;
};

type Paginated<T> = { items: T[]; total: number };

function EventIcon({ type }: { type: string }): React.ReactElement {
  const p = type.toLowerCase();
  if (p.includes("launch")) return <Rocket className="h-5 w-5" />;
  if (p.includes("shift") || p.includes("position")) return <Shuffle className="h-5 w-5" />;
  if (p.includes("agency")) return <Building2 className="h-5 w-5" />;
  if (p.includes("competitor")) return <Swords className="h-5 w-5" />;
  if (p.includes("note") || p.includes("user")) return <StickyNote className="h-5 w-5" />;
  if (p.includes("anomaly") || p.includes("performance")) return <AlertTriangle className="h-5 w-5" />;
  return <CircleDot className="h-5 w-5" />;
}

export function TimelinePage(): React.ReactElement {
  const { brandId } = useBrand();
  const qc = useQueryClient();
  const [eventType, setEventType] = useState("");
  const [source, setSource] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [form, setForm] = useState({
    event_type: "user_note",
    title: "",
    description: "",
    event_date: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
  });

  const timelineQ = useQuery({
    queryKey: ["timeline", brandId, eventType, source, startDate, endDate],
    queryFn: async () => {
      const params: Record<string, string | number | undefined> = {
        page: 1,
        page_size: 50,
        event_type: eventType || undefined,
        source: source || undefined,
      };
      if (startDate) {
        params.start_date = new Date(`${startDate}T00:00:00.000Z`).toISOString();
      }
      if (endDate) {
        params.end_date = new Date(`${endDate}T23:59:59.999Z`).toISOString();
      }
      const { data } = await api.get<Paginated<Item>>(`/api/v1/brands/${brandId}/timeline`, {
        params,
      });
      return data;
    },
    enabled: !!brandId,
  });

  const erasQ = useQuery({
    queryKey: ["eras", brandId],
    queryFn: async () => {
      const { data } = await api.get<
        {
          id: string;
          era_name: string;
          start_date: string;
          context_summary: string | null;
        }[]
      >(`/api/v1/brands/${brandId}/eras`);
      return data;
    },
    enabled: !!brandId,
    retry: false,
  });

  type EraRow = {
    id: string;
    era_name: string;
    start_date: string;
    context_summary: string | null;
  };

  const eraByDate = useMemo(() => {
    const map = new Map<string, EraRow>();
    (erasQ.data ?? []).forEach((e) => map.set(e.start_date.slice(0, 10), e));
    return map;
  }, [erasQ.data]);

  const addM = useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/brands/${brandId}/events`, {
        event_type: form.event_type,
        title: form.title,
        description: form.description || null,
        event_date: new Date(form.event_date).toISOString(),
        impact_tags: [],
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["timeline", brandId] });
      setForm((f) => ({ ...f, title: "", description: "" }));
    },
  });

  if (!brandId) return <p>Select a brand.</p>;

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <div className="mb-4 flex flex-wrap items-end gap-2">
          <div>
            <label className="block text-datalabel text-muted">Event type</label>
            <select
              className="mt-1 rounded border px-2 py-1 text-datalabel"
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
            >
              <option value="">All types</option>
              <option value="product_launch">product_launch</option>
              <option value="positioning_shift">positioning_shift</option>
              <option value="agency_change">agency_change</option>
              <option value="competitor_action">competitor_action</option>
              <option value="user_note">user_note</option>
              <option value="era_boundary">era_boundary</option>
              <option value="profile_computed">profile_computed</option>
            </select>
          </div>
          <div>
            <label className="block text-datalabel text-muted">Source</label>
            <select
              className="mt-1 rounded border px-2 py-1 text-datalabel"
              value={source}
              onChange={(e) => setSource(e.target.value)}
            >
              <option value="">All sources</option>
              <option value="system">system</option>
              <option value="user_provided">user_provided</option>
              <option value="auto_detected">auto_detected</option>
            </select>
          </div>
          <div>
            <label className="block text-datalabel text-muted">From</label>
            <input
              type="date"
              className="mt-1 rounded border px-2 py-1 text-datalabel"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-datalabel text-muted">To</label>
            <input
              type="date"
              className="mt-1 rounded border px-2 py-1 text-datalabel"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
        </div>
        {timelineQ.isLoading ? (
          <div className="h-64 animate-pulse rounded bg-slate-200" />
        ) : (
          <ul className="space-y-3 border-l-2 border-slate-200 pl-4">
            {(timelineQ.data?.items ?? []).map((it) => {
              const day = it.timestamp.slice(0, 10);
              const era = eraByDate.get(day);
              return (
                <li key={`${it.timestamp}-${it.title}`} className="relative">
                  {era && (
                    <div className="mb-2 -ml-4 rounded bg-slate-100 px-3 py-2 text-datalabel">
                      <strong>{era.era_name}</strong>
                      {era.context_summary && <span> — {era.context_summary}</span>}
                    </div>
                  )}
                  <div className="flex gap-3">
                    <div className="-ml-[1.35rem] mt-1 flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600">
                      <EventIcon type={it.event_type} />
                    </div>
                    <div className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white p-3">
                      <p className="text-datalabel text-muted">
                        {format(new Date(it.timestamp), "PPp")} · {it.source}
                      </p>
                      <p className="text-cardtitle">{it.title}</p>
                      {it.description && (
                        <p className="mt-1 line-clamp-2 text-body text-muted">{it.description}</p>
                      )}
                      {it.impact && Object.keys(it.impact).length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {Object.entries(it.impact)
                            .slice(0, 8)
                            .map(([ik, iv]) => (
                              <span
                                key={ik}
                                className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                              >
                                {ik}: {String(iv).slice(0, 24)}
                                {String(iv).length > 24 ? "…" : ""}
                              </span>
                            ))}
                        </div>
                      )}
                      <details className="mt-2">
                        <summary className="cursor-pointer text-datalabel text-accent">Expand</summary>
                        <p className="mt-2 text-body">{it.description}</p>
                        <pre className="mt-2 overflow-x-auto text-xs">
                          {JSON.stringify(it.related_data, null, 2)}
                        </pre>
                      </details>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="text-cardtitle">Add event</h3>
        <form
          className="mt-3 space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            addM.mutate();
          }}
        >
          <select
            className="w-full rounded border px-2 py-1"
            value={form.event_type}
            onChange={(e) => setForm((f) => ({ ...f, event_type: e.target.value }))}
          >
            <option value="user_note">user_note</option>
            <option value="product_launch">product_launch</option>
            <option value="positioning_shift">positioning_shift</option>
            <option value="agency_change">agency_change</option>
            <option value="competitor_action">competitor_action</option>
          </select>
          <input
            required
            className="w-full rounded border px-2 py-1"
            placeholder="Title"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
          />
          <textarea
            className="w-full rounded border px-2 py-1"
            placeholder="Description"
            rows={3}
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          />
          <input
            type="datetime-local"
            className="w-full rounded border px-2 py-1"
            value={form.event_date}
            onChange={(e) => setForm((f) => ({ ...f, event_date: e.target.value }))}
          />
          <button type="submit" className="w-full rounded bg-accent py-2 text-white">
            Save event
          </button>
        </form>
      </div>
    </div>
  );
}
