"use client";

import { useEffect, useState } from "react";
import { listDatasets, uploadDataset } from "@/lib/api";
import type { Dataset } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Loader2, Upload, FileText, AlertCircle, CheckCircle2, FolderOpen } from "lucide-react";

function ValidationBadge({ status }: { status: string }) {
  const variants: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
    valid: { label: "Valid", variant: "default" },
    invalid: { label: "Invalid", variant: "destructive" },
    pending: { label: "Pending", variant: "outline" },
  };
  const config = variants[status] ?? { label: status, variant: "outline" as const };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    listDatasets().then(setDatasets).catch(console.error);
  }, []);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!file) {
      setError("Please select a file");
      return;
    }

    if (file.size > 500 * 1024 * 1024) {
      setError("File exceeds maximum size of 500 MB");
      return;
    }

    setUploading(true);
    try {
      const dataset = await uploadDataset(file, name || file.name);
      setDatasets((prev) => [dataset, ...prev]);
      setName("");
      setFile(null);
      (e.target as HTMLFormElement).reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Datasets"
        description="Upload and manage your training datasets"
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Upload Dataset
          </CardTitle>
          <CardDescription>
            Supported formats: JSONL, CSV, TXT. Max 500 MB, 100,000 rows.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleUpload} className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="name">Name (optional)</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My dataset"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="file">File</Label>
              <Input
                id="file"
                type="file"
                accept=".jsonl,.csv,.txt"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                required
              />
            </div>
            <Button type="submit" disabled={uploading}>
              {uploading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {uploading ? "Uploading..." : "Upload"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Separator />

      {datasets.length === 0 ? (
        <EmptyState
          icon={<FolderOpen className="h-12 w-12" />}
          title="No datasets yet"
          description="Upload your first dataset to get started."
        />
      ) : (
        <div className="space-y-3">
          {datasets.map((d) => (
            <Card key={d.id} className="hover:shadow-sm transition-shadow">
              <CardContent className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <div className="font-medium text-sm">{d.name}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {d.format.toUpperCase()} · {(d.size_bytes / 1024 / 1024).toFixed(1)} MB
                      {d.row_count != null ? ` · ${d.row_count.toLocaleString()} rows` : ""}
                    </div>
                  </div>
                </div>
                <ValidationBadge status={d.validation_status} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
