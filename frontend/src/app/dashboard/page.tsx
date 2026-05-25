"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, getBalance } from "@/lib/api";
import type { Job, BalanceResponse } from "@/types";

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

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);

  useEffect(() => {
    listJobs().then(setJobs).catch(console.error);
    getBalance().then(setBalance).catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {balance && (
        <div className="bg-card border rounded-lg p-4">
          <div className="text-sm text-muted-foreground">Credit Balance</div>
          <div className="text-3xl font-bold mt-1">${balance.balance.toFixed(2)}</div>
          <Link href="/dashboard/credits" className="text-sm text-primary mt-2 inline-block">
            Add credits →
          </Link>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Recent Jobs</h2>
          <Link href="/dashboard/new-job" className="text-sm text-primary">
            New job →
          </Link>
        </div>

        {jobs.length === 0 ? (
          <p className="text-muted-foreground text-sm">No jobs yet. Create your first fine-tuning job.</p>
        ) : (
          <div className="space-y-2">
            {jobs.slice(0, 5).map((job) => (
              <div key={job.id} className="border rounded-lg p-4 flex items-center justify-between">
                <div>
                  <div className="font-medium text-sm">Job {job.id.slice(0, 8)}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {job.adapter.toUpperCase()} · {job.preset} · {job.created_at.slice(0, 10)}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {job.estimated_cost && (
                    <span className="text-sm text-muted-foreground">${job.estimated_cost}</span>
                  )}
                  <span
                    className={`text-xs px-2 py-1 rounded-full font-medium ${statusColors[job.status] || "bg-gray-100"}`}
                  >
                    {job.status}
                  </span>
                  <Link href={`/dashboard/jobs/${job.id}`} className="text-sm text-primary">
                    Details
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
