"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, getBalance } from "@/lib/api";
import type { Job, BalanceResponse } from "@/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { StatusBadge } from "@/components/status-badge";
import { EmptyState } from "@/components/empty-state";
import { Coins, ListTodo, PlusCircle, ArrowRight } from "lucide-react";

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);

  useEffect(() => {
    let mounted = true;
    listJobs().then((data) => { if (mounted) setJobs(data); }).catch(() => {});
    getBalance().then((data) => { if (mounted) setBalance(data); }).catch(() => {});
    return () => { mounted = false; };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Manage your fine-tuning jobs and datasets
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Credit Balance</CardTitle>
            <Coins className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${balance?.balance.toFixed(2) ?? "0.00"}
            </div>
            <Button asChild variant="link" className="p-0 h-auto mt-2 text-sm">
              <Link href="/dashboard/credits">
                Add credits <ArrowRight className="ml-1 h-3 w-3" />
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Jobs</CardTitle>
            <ListTodo className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{jobs.length}</div>
            <Button asChild variant="link" className="p-0 h-auto mt-2 text-sm">
              <Link href="/dashboard/jobs">
                View all <ArrowRight className="ml-1 h-3 w-3" />
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Quick Start</CardTitle>
            <PlusCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Button asChild className="w-full">
              <Link href="/dashboard/new-job">
                <PlusCircle className="mr-2 h-4 w-4" />
                New Job
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      <Separator />

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Recent Jobs</h2>
          <Button asChild variant="ghost" size="sm">
            <Link href="/dashboard/new-job">
              <PlusCircle className="mr-2 h-4 w-4" />
              New job
            </Link>
          </Button>
        </div>

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
            {jobs.slice(0, 5).map((job) => (
              <Card key={job.id} className="hover:shadow-sm transition-shadow">
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <div className="font-medium text-sm">
                      Job {job.id.slice(0, 8)}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {job.adapter.toUpperCase()} · {job.preset} · {job.created_at.slice(0, 10)}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {job.estimated_cost && (
                      <span className="text-sm text-muted-foreground">
                        ${job.estimated_cost}
                      </span>
                    )}
                    <StatusBadge status={job.status} />
                    <Button asChild variant="ghost" size="sm">
                      <Link href={`/dashboard/jobs/${job.id}`}>
                        Details
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
