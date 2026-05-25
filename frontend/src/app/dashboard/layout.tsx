"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getMe } from "@/lib/api";
import type { User } from "@/types";

const navItems = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/datasets", label: "Datasets" },
  { href: "/dashboard/jobs", label: "Jobs" },
  { href: "/dashboard/new-job", label: "New Job" },
  { href: "/dashboard/credits", label: "Credits" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    getMe().then(setUser).catch(() => router.push("/login"));
  }, [router]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <Link href="/dashboard" className="text-xl font-bold">OpenReef</Link>
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">
            Balance: ${user.balance.toFixed(2)}
          </span>
          <button
            onClick={() => {
              localStorage.removeItem("token");
              router.push("/login");
            }}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Logout
          </button>
        </div>
      </header>

      <div className="flex flex-1">
        <nav className="w-48 border-r p-4 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`block px-3 py-2 rounded-md text-sm ${
                pathname === item.href
                  ? "bg-accent font-medium"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <main className="flex-1 p-6">{children}</main>
      </div>

      <footer className="border-t px-6 py-3 text-xs text-muted-foreground flex justify-between">
        <span>OpenReef MVP</span>
        <a href="https://t.me/openreef" target="_blank" className="hover:text-foreground">
          Need help? Join our Telegram
        </a>
      </footer>
    </div>
  );
}
