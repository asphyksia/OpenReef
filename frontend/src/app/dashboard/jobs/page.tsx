"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, cancelJob } from "@/lib/api";
import type { Job } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { EmptyState } from "@/components/empty-state";
import { LoadingSkeleton } from "@/components/loading-skeleton";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { PageHeader } from "@/components/page-header";
import { PlusCircle, ListTodo, Loader2 } from "lucide-react";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [cancelId, setCancelId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleCancel() {
    if (!cancelId) return;
    setCancelling(true);
    try {
      const updated = await cancelJob(cancelId);
      setJobs((prev) => prev.map((j) => (j.id === cancelId ? updated : j)));
    } catch (err) {
      console.error("Failed to cancel job:", err);
    } finally {
      setCancelling(false);
      setCancelId(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Jobs" description="Manage your fine-tuning jobs" />
        <LoadingSkeleton rows={4} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Jobs"
        description="Manage your fine-tuning jobs"
        action={
          <Button asChild>
            <Link href="/dashboard/new-job">
              <PlusCircle className="mr-2 h-4 w-4" />
              New Job
            </Link>
          </Button>
        }
      />

      {jobs.length === 0 ? (
        <EmptyState
          icon={<ListTodo className="h-12 w-12" />}
          title="No jobs yet"
          description="Create your first fine-tuning job to get started."
          action={
            <Button asChild>
              <Link href="/dashboard/new-job">
                <PlusCircle className="mr-2 h-4 w-4" />
                Create job
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <Card key={job.id} className="hover:shadow-sm transition-shadow">
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <Link
                    href={`/dashboard/jobs/${job.id}`}
                    className="font-medium text-sm text-primary hover:underline"
                  >
                    Job {job.id.slice(0, 8)}
                  </Link>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {job.adapter.toUpperCase()} · {job.preset} · {job.created_at.slice(0, 10)}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <StatusBadge status={job.status} />
                  {["pending", "queued", "provisioning", "running"].includes(job.status) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setCancelId(job.id)}
                    >
                      Cancel
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={cancelId !== null}
        onOpenChange={(open) => !open && setCancelId(null)}
        title="Cancel job"
        description="Are you sure you want to cancel this job? If already charged, credits will be refunded based on the current phase."
        confirmText="Cancel job"
        cancelText="Keep running"
        onConfirm={handleCancel}
        variant="destructive"
      />
    </div>
  );
}
