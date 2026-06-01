"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getJob, confirmJob, cancelJob } from "@/lib/api";
import type { Job } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { StatusBadge } from "@/components/status-badge";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { PageHeader } from "@/components/page-header";
import { LoadingSkeleton } from "@/components/loading-skeleton";
import {
  Loader2,
  Download,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Clock,
  DollarSign,
  Settings,
  Calendar,
} from "lucide-react";

function formatETA(eta: string): string {
  const target = new Date(eta);
  const now = new Date();
  const diffMs = target.getTime() - now.getTime();
  if (diffMs <= 0) return "now";
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `~${mins}m`;
  const hours = Math.floor(mins / 60);
  const rem = mins % 60;
  return `~${hours}h ${rem}m`;
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);

  useEffect(() => {
    getJob(params.id as string)
      .then(setJob)
      .catch(() => router.push("/dashboard/jobs"))
      .finally(() => setLoading(false));
  }, [params.id, router]);

  useEffect(() => {
    if (!job) return;
    if (!["pending", "queued", "provisioning", "running"].includes(job.status)) return;

    const interval = setInterval(() => {
      getJob(params.id as string).then(setJob).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [job?.status, params.id]);

  async function handleConfirm() {
    setActionLoading(true);
    try {
      const updated = await confirmJob(params.id as string);
      setJob(updated);
    } catch (err) {
      console.error("Failed to confirm job:", err);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    setActionLoading(true);
    try {
      const updated = await cancelJob(params.id as string);
      setJob(updated);
    } catch (err) {
      console.error("Failed to cancel job:", err);
    } finally {
      setActionLoading(false);
      setShowCancelDialog(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6 max-w-2xl">
        <PageHeader title="Job Details" />
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (!job) return null;

  const getRefundMessage = (status: string) => {
    switch (status) {
      case "pending":
        return "This will refund 100% of your credits.";
      case "queued":
        return "This will refund 50% of your credits (50% retained for provider reservation).";
      default:
        return "This will NOT refund any credits (provider has reserved hardware).";
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader
        title={`Job ${job.id.slice(0, 8)}`}
        description={job.status_detail || `Created on ${job.created_at.slice(0, 10)}`}
      />

      <div className="flex items-center justify-between">
        <StatusBadge status={job.status} />
        {job.estimated_completion && (
          <div className="flex items-center gap-1 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            ETA: {formatETA(job.estimated_completion)}
          </div>
        )}
      </div>

      {job.error_message && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{job.error_message}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Job Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Settings className="h-4 w-4" />
              Adapter
            </div>
            <div className="font-medium text-right">{job.adapter.toUpperCase()}</div>

            <div className="flex items-center gap-2 text-muted-foreground">
              <DollarSign className="h-4 w-4" />
              Preset
            </div>
            <div className="font-medium text-right capitalize">{job.preset}</div>

            <div className="flex items-center gap-2 text-muted-foreground">
              <DollarSign className="h-4 w-4" />
              Estimated Cost
            </div>
            <div className="font-medium text-right">
              ${job.estimated_cost?.toFixed(2) ?? "—"}
            </div>

            <div className="flex items-center gap-2 text-muted-foreground">
              <DollarSign className="h-4 w-4" />
              Actual Cost
            </div>
            <div className="font-medium text-right">
              ${job.actual_cost?.toFixed(2) ?? "—"}
            </div>

            <div className="flex items-center gap-2 text-muted-foreground">
              <Calendar className="h-4 w-4" />
              Created
            </div>
            <div className="text-right">{job.created_at.slice(0, 19)}</div>

            {job.started_at && (
              <>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  Started
                </div>
                <div className="text-right">{job.started_at.slice(0, 19)}</div>
              </>
            )}

            {job.completed_at && (
              <>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  Completed
                </div>
                <div className="text-right">{job.completed_at.slice(0, 19)}</div>
              </>
            )}
          </div>

          <Separator />

          <div>
            <div className="flex items-center justify-between mb-2 text-sm">
              <span className="text-muted-foreground">Progress</span>
              <span className="font-medium">{job.progress_pct}%</span>
            </div>
            <Progress value={job.progress_pct} className="h-2" />
          </div>

          {job.ogpu_task_address && (
            <>
              <Separator />
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">OGPU Task</span>
                <a
                  href={`https://client.opengpu.network/tasks/${job.ogpu_task_address}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-primary hover:underline font-mono"
                >
                  {job.ogpu_task_address.slice(0, 10)}...
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {job.download_url && (
        <Card className="border-green-500/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-600">
              <CheckCircle2 className="h-5 w-5" />
              Training Complete
            </CardTitle>
            <CardDescription>
              Your model adapter is ready for download
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <a href={job.download_url} download>
                <Download className="mr-2 h-4 w-4" />
                Download Model
              </a>
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              Download link expires in 1 hour
            </p>
          </CardContent>
        </Card>
      )}

      <div className="flex gap-3">
        {job.status === "pending" && (
          <Button onClick={handleConfirm} disabled={actionLoading}>
            {actionLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {actionLoading ? "Confirming..." : "Confirm & Start Job"}
          </Button>
        )}
        {["pending", "queued", "provisioning"].includes(job.status) && (
          <Button
            variant="outline"
            className="border-destructive text-destructive hover:bg-destructive/10"
            onClick={() => setShowCancelDialog(true)}
            disabled={actionLoading}
          >
            Cancel Job
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={showCancelDialog}
        onOpenChange={setShowCancelDialog}
        title="Cancel job"
        description={job ? getRefundMessage(job.status) : ""}
        confirmText="Cancel job"
        cancelText="Keep running"
        onConfirm={handleCancel}
        variant="destructive"
      />
    </div>
  );
}
