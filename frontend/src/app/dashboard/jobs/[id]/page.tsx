"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getJob, confirmJob, cancelJob } from "@/lib/api";
import type { Job } from "@/types";

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

const statusColors: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  queued: "bg-blue-100 text-blue-800",
  provisioning: "bg-purple-100 text-purple-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-800",
  refunded: "bg-orange-100 text-orange-800",
};

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    getJob(params.id as string)
      .then(setJob)
      .catch(() => router.push("/dashboard/jobs"))
      .finally(() => setLoading(false));
  }, [params.id, router]);

  // Poll for active jobs
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
      alert(err instanceof Error ? err.message : "Failed to confirm job");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    const refundMsg =
      job.status === "pending"
        ? "This will refund 100% of your credits."
        : job.status === "queued"
          ? "This will refund 50% of your credits (50% retained for provider reservation)."
          : "This will NOT refund any credits (provider has reserved hardware).";
    if (!confirm(`Cancel this job?\n${refundMsg}`)) return;
    setActionLoading(true);
    try {
      const updated = await cancelJob(params.id as string);
      setJob(updated);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to cancel job");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <p className="text-muted-foreground">Loading...</p>;
  if (!job) return null;

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Job {job.id.slice(0, 8)}</h1>
        <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusColors[job.status] || "bg-gray-100"}`}>
          {job.status}
        </span>
      </div>

      {job.status_detail && (
        <p className="text-sm text-muted-foreground">{job.status_detail}</p>
      )}

      {job.error_message && (
        <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md">
          {job.error_message}
        </div>
      )}

      <div className="border rounded-lg divide-y">
        <div className="p-4 flex justify-between">
          <span className="text-sm text-muted-foreground">Adapter</span>
          <span className="text-sm font-medium">{job.adapter.toUpperCase()}</span>
        </div>
        <div className="p-4 flex justify-between">
          <span className="text-sm text-muted-foreground">Preset</span>
          <span className="text-sm font-medium capitalize">{job.preset}</span>
        </div>
        <div className="p-4 flex justify-between">
          <span className="text-sm text-muted-foreground">Estimated Cost</span>
          <span className="text-sm font-medium">${job.estimated_cost?.toFixed(2) ?? "—"}</span>
        </div>
        <div className="p-4 flex justify-between">
          <span className="text-sm text-muted-foreground">Actual Cost</span>
          <span className="text-sm font-medium">${job.actual_cost?.toFixed(2) ?? "—"}</span>
        </div>
        <div className="p-4 flex justify-between items-center">
          <span className="text-sm text-muted-foreground">Progress</span>
          <div className="flex items-center gap-2">
            {job.estimated_completion && (
              <span className="text-xs text-muted-foreground">ETA: {formatETA(job.estimated_completion)}</span>
            )}
            <span className="text-sm font-medium">{job.progress_pct}%</span>
          </div>
        </div>
        {job.progress_pct > 0 && (
          <div className="p-4">
            <div className="w-full bg-secondary rounded-full h-2 overflow-hidden">
              <div
                className="bg-primary h-2 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(job.progress_pct, 100)}%` }}
              />
            </div>
          </div>
        )}
        <div className="p-4 flex justify-between">
          <span className="text-sm text-muted-foreground">OGPU Task</span>
          {job.ogpu_task_address ? (
            <a
              href={`https://client.opengpu.network/tasks/${job.ogpu_task_address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline font-mono"
            >
              {job.ogpu_task_address.slice(0, 10)}...
            </a>
          ) : (
            <span className="text-sm text-muted-foreground">—</span>
          )}
        </div>
        <div className="p-4 flex justify-between">
          <span className="text-sm text-muted-foreground">Created</span>
          <span className="text-sm">{job.created_at.slice(0, 19)}</span>
        </div>
        {job.started_at && (
          <div className="p-4 flex justify-between">
            <span className="text-sm text-muted-foreground">Started</span>
            <span className="text-sm">{job.started_at.slice(0, 19)}</span>
          </div>
        )}
        {job.completed_at && (
          <div className="p-4 flex justify-between">
            <span className="text-sm text-muted-foreground">Completed</span>
            <span className="text-sm">{job.completed_at.slice(0, 19)}</span>
          </div>
        )}
        {job.download_url && (
          <div className="p-4">
            <span className="text-sm text-muted-foreground block mb-2">Download Artifact</span>
            <a
              href={job.download_url}
              download
              className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
              Download Model
            </a>
            <p className="text-xs text-muted-foreground mt-2">
              Download link expires in 1 hour
            </p>
          </div>
        )}
      </div>

      <div className="flex gap-3">
        {job.status === "pending" && (
          <button
            onClick={handleConfirm}
            disabled={actionLoading}
            className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {actionLoading ? "Confirming..." : "Confirm & Start Job"}
          </button>
        )}
        {["pending", "queued", "provisioning"].includes(job.status) && (
          <button
            onClick={handleCancel}
            disabled={actionLoading}
            className="border border-destructive text-destructive px-4 py-2 rounded-md text-sm font-medium hover:bg-destructive/10 disabled:opacity-50"
          >
            {actionLoading ? "Cancelling..." : "Cancel"}
          </button>
        )}
      </div>
    </div>
  );
}
