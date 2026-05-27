"use client";

import { useEffect, useState } from "react";
import { listDatasets, uploadDataset } from "@/lib/api";
import type { Dataset } from "@/types";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listDatasets().then(setDatasets).catch(console.error);
  }, []);

  async function handleUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setUploading(true);

    const form = new FormData(e.currentTarget);
    const file = form.get("file") as File;
    const name = (form.get("name") as string) || file.name;

    if (file.size > 500 * 1024 * 1024) {
      setError("File exceeds maximum size of 500 MB");
      setUploading(false);
      return;
    }

    try {
      const dataset = await uploadDataset(file, name);
      setDatasets((prev) => [dataset, ...prev]);
      (e.target as HTMLFormElement).reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Datasets</h1>

      <div className="border rounded-lg p-4">
        <h2 className="text-sm font-semibold mb-3">Upload Dataset</h2>
        <p className="text-xs text-muted-foreground mb-3">
          Supported formats: JSONL, CSV, TXT. Max 500 MB, 100,000 rows.
        </p>

        {error && (
          <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md mb-3">{error}</div>
        )}

        <form onSubmit={handleUpload} className="space-y-3">
          <div>
            <label className="text-sm font-medium">Name (optional)</label>
            <input
              name="name"
              type="text"
              placeholder="My dataset"
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-sm font-medium">File</label>
            <input
              name="file"
              type="file"
              accept=".jsonl,.csv,.txt"
              required
              className="mt-1 w-full text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={uploading}
            className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </form>
      </div>

      <div className="space-y-2">
        {datasets.length === 0 ? (
          <p className="text-muted-foreground text-sm">No datasets uploaded yet.</p>
        ) : (
          datasets.map((d) => (
            <div key={d.id} className="border rounded-lg p-4 flex items-center justify-between">
              <div>
                <div className="font-medium text-sm">{d.name}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {d.format.toUpperCase()} · {(d.size_bytes / 1024 / 1024).toFixed(1)} MB
                  {d.row_count != null ? ` · ${d.row_count.toLocaleString()} rows` : ""}
                </div>
              </div>
              <span
                className={`text-xs px-2 py-1 rounded-full font-medium ${
                  d.validation_status === "valid"
                    ? "bg-green-100 text-green-800"
                    : d.validation_status === "invalid"
                      ? "bg-red-100 text-red-800"
                      : "bg-yellow-100 text-yellow-800"
                }`}
              >
                {d.validation_status}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
