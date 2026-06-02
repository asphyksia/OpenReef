"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getMe, logout } from "@/lib/api";
import type { User } from "@/types";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  LayoutDashboard,
  FolderOpen,
  ListTodo,
  PlusCircle,
  Coins,
  LogOut,
  MessageCircle,
  Sun,
  Moon,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/datasets", label: "Datasets", icon: FolderOpen },
  { href: "/dashboard/jobs", label: "Jobs", icon: ListTodo },
  { href: "/dashboard/new-job", label: "New Job", icon: PlusCircle },
  { href: "/dashboard/credits", label: "Credits", icon: Coins },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    // Restore dark mode preference from localStorage
    const stored = localStorage.getItem("darkMode");
    if (stored !== null) {
      const isDark = stored === "true";
      document.documentElement.classList.toggle("dark", isDark);
      setDarkMode(isDark);
    }
  }, []);

  useEffect(() => {
    const fetchUser = () => getMe().then(setUser).catch(() => router.push("/login"));
    fetchUser();
    // Refresh user data (balance) every 30 seconds
    const interval = setInterval(fetchUser, 30000);
    return () => clearInterval(interval);
  }, [router]);

  function toggleDarkMode() {
    const next = !darkMode;
    document.documentElement.classList.toggle("dark", next);
    setDarkMode(next);
    localStorage.setItem("darkMode", String(next));
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-muted-foreground text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  const initials = user.email.slice(0, 2).toUpperCase();

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="border-b px-6 py-3 flex items-center justify-between bg-card">
        <Link href="/dashboard" className="text-xl font-bold tracking-tight">
          OpenReef
        </Link>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Coins className="h-4 w-4" />
            <span className="font-medium text-foreground">${user.balance.toFixed(2)}</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleDarkMode}
            className="h-8 w-8"
          >
            {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <Avatar className="h-8 w-8">
            <AvatarFallback className="text-xs font-medium bg-primary text-primary-foreground">
              {initials}
            </AvatarFallback>
          </Avatar>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => logout().finally(() => router.push("/login"))}
            className="gap-2"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">Logout</span>
          </Button>
        </div>
      </header>

      <div className="flex flex-1">
        <nav className="w-52 border-r bg-card p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-accent font-medium text-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <main className="flex-1 p-6">{children}</main>
      </div>

      <footer className="border-t px-6 py-3 text-xs text-muted-foreground flex justify-between bg-card">
        <span>OpenReef MVP</span>
        <a
          href="https://t.me/openreef"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 hover:text-foreground transition-colors"
        >
          <MessageCircle className="h-3 w-3" />
          Need help? Join our Telegram
        </a>
      </footer>
    </div>
  );
}
