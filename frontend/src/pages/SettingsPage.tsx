import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useBrand } from "../contexts/BrandContext";

type Brand = {
  id: string;
  name: string;
  industry: string | null;
  description: string | null;
  website_url: string | null;
  success_metrics: unknown[];
};

export function SettingsPage(): React.ReactElement {
  const { brandId } = useBrand();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["brand", brandId],
    queryFn: async () => {
      const { data } = await api.get<Brand>("/api/v1/brands/" + brandId);
      return data;
    },
    enabled: !!brandId,
  });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    if (q.data) {
      setName(q.data.name);
      setDescription(q.data.description ?? "");
    }
  }, [q.data]);

  const save = useMutation({
    mutationFn: async () => {
      await api.patch("/api/v1/brands/" + brandId, { name, description: description || null });
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["brand", brandId] }),
  });

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const inviteM = useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/brands/${brandId}/members`, {
        email: inviteEmail,
        role: inviteRole,
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["brand", brandId] });
      setInviteEmail("");
    },
  });

  const guidelinesM = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      await api.post(`/api/v1/brands/${brandId}/guidelines`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["brand", brandId] }),
  });

  if (!brandId) return <p className="text-muted">Select a brand.</p>;
  if (q.isLoading) return <div className="h-40 animate-pulse rounded bg-slate-200" />;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-section">Brand</h3>
        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <div>
            <label className="text-datalabel text-muted">Name</label>
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
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
          <button
            type="submit"
            className="rounded bg-accent px-4 py-2 text-white"
            disabled={save.isPending}
          >
            Save
          </button>
        </form>
      </section>
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-section">Team invite</h3>
        <p className="mt-1 text-datalabel text-muted">
          User must already be registered. Owner-only API.
        </p>
        <form
          className="mt-3 flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            inviteM.mutate();
          }}
        >
          <input
            type="email"
            required
            className="min-w-[200px] flex-1 rounded border px-3 py-2"
            placeholder="colleague@company.com"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
          />
          <select
            className="rounded border px-2 py-2"
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
          >
            <option value="viewer">viewer</option>
            <option value="editor">editor</option>
            <option value="owner">owner</option>
          </select>
          <button
            type="submit"
            className="rounded bg-accent px-4 py-2 text-white"
            disabled={inviteM.isPending}
          >
            Invite
          </button>
        </form>
        {inviteM.isError && (
          <p className="mt-2 text-datalabel text-danger">
            Invite failed (user may not exist or already a member).
          </p>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-section">Brand guidelines</h3>
        <p className="mt-1 text-datalabel text-muted">Upload PDF or document (API limit applies).</p>
        <input
          type="file"
          className="mt-2 block text-datalabel"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) guidelinesM.mutate(f);
          }}
        />
        {guidelinesM.isSuccess && (
          <p className="mt-2 text-datalabel text-success">Uploaded.</p>
        )}
      </section>

      <section className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6">
        <h3 className="text-cardtitle">Connected platforms</h3>
        <p className="mt-2 text-datalabel text-muted">Coming in a later release.</p>
      </section>
    </div>
  );
}
