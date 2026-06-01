"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listDatasets, listModels, createJob } from "@/lib/api";
import type { Dataset, ModelsResponse } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { LoadingSkeleton } from "@/components/loading-skeleton";
import { Loader2, AlertCircle, Settings, Zap, Brain, Database } from "lucide-react";

const presetIcons: Record<string, React.ReactNode> = {
  fast: <Zap className="h-4 w-4" />,
  balanced: <Settings className="h-4 w-4" />,
  quality: <Brain className="h-4 w-4" />,
};

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

  if (loading) {
    return (
      <div className="space-y-6 max-w-xl">
        <PageHeader title="New Fine-tuning Job" />
        <LoadingSkeleton rows={5} />
      </div>
    );
  }

  const validDatasets = datasets.filter((d) => d.validation_status === "valid");

  return (
    <div className="space-y-6 max-w-xl">
      <PageHeader
        title="New Fine-tuning Job"
        description="Configure your training job"
      />

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Dataset
            </CardTitle>
          </CardHeader>
          <CardContent>
            {validDatasets.length === 0 ? (
              <EmptyState
                icon={<Database className="h-8 w-8" />}
                title="No valid datasets"
                description="Upload a valid dataset before creating a job."
                action={
                  <Button asChild variant="outline">
                    <a href="/dashboard/datasets">Upload dataset</a>
                  </Button>
                }
              />
            ) : (
              <Select value={datasetId} onValueChange={setDatasetId} required>
                <SelectTrigger>
                  <SelectValue placeholder="Select a dataset..." />
                </SelectTrigger>
                <SelectContent>
                  {validDatasets.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.name} ({d.format}, {d.row_count?.toLocaleString() ?? 0} rows)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              Base Model
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={baseModelId} onValueChange={setBaseModelId} required>
              <SelectTrigger>
                <SelectValue placeholder="Select a model..." />
              </SelectTrigger>
              <SelectContent>
                {modelsData?.models.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.name} ({m.param_count}B, min {m.min_vram_gb}GB VRAM)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Training Preset
            </CardTitle>
            <CardDescription>
              Choose a preset based on your needs
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RadioGroup value={preset} onValueChange={setPreset} className="space-y-3">
              {modelsData &&
                Object.entries(modelsData.presets).map(([key, p]) => (
                  <Label
                    key={key}
                    className={`flex items-start gap-3 border rounded-lg p-4 cursor-pointer transition-colors ${
                      preset === key ? "border-primary bg-accent" : "hover:bg-accent/50"
                    }`}
                  >
                    <RadioGroupItem value={key} className="mt-1" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        {presetIcons[key]}
                        {p.label}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">{p.description}</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {p.epochs} epoch{p.epochs > 1 ? "s" : ""} · LR {p.learning_rate}
                      </div>
                    </div>
                  </Label>
                ))}
            </RadioGroup>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Adapter Type</CardTitle>
          </CardHeader>
          <CardContent>
            <RadioGroup value={adapter} onValueChange={setAdapter} className="flex gap-6">
              <Label className="flex items-center gap-2 cursor-pointer">
                <RadioGroupItem value="lora" />
                <span className="text-sm font-medium">LoRA</span>
              </Label>
              <Label className="flex items-center gap-2 cursor-pointer">
                <RadioGroupItem value="qlora" />
                <span className="text-sm font-medium">QLoRA</span>
              </Label>
            </RadioGroup>
            {adapter === "qlora" && (
              <Alert className="mt-4 border-amber-500/50 bg-amber-50 dark:bg-amber-950/20">
                <AlertCircle className="h-4 w-4 text-amber-600" />
                <AlertDescription className="text-amber-700 dark:text-amber-400 text-sm">
                  QLoRA requires NVIDIA GPUs. On AMD ROCm providers, it will automatically fall back to LoRA.
                  LoRA uses more VRAM but produces identical results.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        <Separator />

        <Button
          type="submit"
          className="w-full"
          disabled={submitting || !datasetId || !baseModelId}
        >
          {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {submitting ? "Creating job..." : "Create Job"}
        </Button>
      </form>
    </div>
  );
}
