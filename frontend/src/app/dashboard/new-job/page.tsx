"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listDatasets, listModels, createJob } from "@/lib/api";
import type { Dataset, ModelsResponse } from "@/types";

export default function NewJobPage() {
  const router = useRouter();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [modelsData, setModelsData] = useState<ModelsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const [datasetId, setDatasetId] = useState("");
  const [baseModelId, setBaseModelId] = useState("");
  const [preset, setPreset] = useState("balanced");
  const [adapter, setAdapter] = useState("lora");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    Promise.all([listDatasets(), listModels()])
      .then(([d, m]) => {
        setDatasets(d);
        setModelsData(m);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const job = await createJob({ dataset_id: datasetId, base_model_id: baseModelId, preset, adapter });
      router.push(`/dashboard/jobs/${job.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p className="text-muted-foreground">Loading...</p>;

  const validDatasets = datasets.filter((d) => d.validation_status === "valid");

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-2xl font-bold">New Fine-tuning Job</h1>

      {error && (
        <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 border rounded-lg p-6">
        <div>
          <label className="text-sm font-medium">Dataset</label>
          {validDatasets.length === 0 ? (
            <p className="text-sm text-muted-foreground mt-1">
              No valid datasets.{" "}
              <a href="/dashboard/datasets" className="text-primary hover:underline">Upload one first</a>.
            </p>
          ) : (
            <select
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              required
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
            >
              <option value="">Select a dataset...</option>
              {validDatasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.format}, {d.row_count?.toLocaleString() ?? 0} rows)
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <label className="text-sm font-medium">Base Model</label>
          <select
            value={baseModelId}
            onChange={(e) => setBaseModelId(e.target.value)}
            required
            className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
          >
            <option value="">Select a model...</option>
            {modelsData?.models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.param_count}B, min {m.min_vram_gb}GB VRAM)
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-sm font-medium">Preset</label>
          <div className="mt-2 space-y-2">
            {modelsData &&
              Object.entries(modelsData.presets).map(([key, p]) => (
                <label
                  key={key}
                  className={`flex items-start gap-3 border rounded-md p-3 cursor-pointer ${
                    preset === key ? "border-primary bg-accent" : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="preset"
                    value={key}
                    checked={preset === key}
                    onChange={(e) => setPreset(e.target.value)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-sm font-medium">{p.label}</div>
                    <div className="text-xs text-muted-foreground">{p.description}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {p.epochs} epoch{p.epochs > 1 ? "s" : ""} · LR {p.learning_rate}
                    </div>
                  </div>
                </label>
              ))}
          </div>
        </div>

        <div>
          <label className="text-sm font-medium">Adapter</label>
          <div className="mt-2 flex gap-4">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="adapter"
                value="lora"
                checked={adapter === "lora"}
                onChange={(e) => setAdapter(e.target.value)}
              />
              <span className="text-sm">LoRA</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="adapter"
                value="qlora"
                checked={adapter === "qlora"}
                onChange={(e) => setAdapter(e.target.value)}
              />
              <span className="text-sm">QLoRA</span>
            </label>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting || !datasetId || !baseModelId}
          className="w-full bg-primary text-primary-foreground py-2 rounded-md font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {submitting ? "Creating..." : "Create Job"}
        </button>
      </form>
    </div>
  );
}
