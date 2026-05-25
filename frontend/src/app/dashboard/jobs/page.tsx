"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, cancelJob } from "@/lib/api";
import type { Job } from "@/types";

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

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleCancel(id: string) {
    if (!confirm("Cancel this job? If already charged, credits will be refunded.")) return;
    const updated = await cancelJob(id);
    setJobs((prev) => prev.map((j) => (j.id === id ? updated : j)));
  }

  if (loading) return <p className="text-muted-foreground">Loading...</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Jobs</h1>
        <Link href="/dashboard/new-job" className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90">
          New Job
        </Link>
      </div>

      {jobs.length === 0 ? (
        <p className="text-muted-foreground text-sm">No jobs yet.</p>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <div key={job.id} className="border rounded-lg p-4 flex items-center justify-between">
              <div>
                <Link href={`/dashboard/jobs/${job.id}`} className="font-medium text-sm text-primary hover:underline">
                  Job {job.id.slice(0, 8)}
                </Link>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {job.adapter.toUpperCase()} · {job.preset} · {job.created_at.slice(0, 10)}
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusColors[job.status] || "bg-gray-100"}`}>
                  {job.status}
                </span>
                {["pending", "queued", "provisioning"].includes(job.status) && (
                  <button
                    onClick={() => handleCancel(job.id)}
                    className="text-xs text-destructive hover:underline"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
