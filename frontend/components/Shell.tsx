"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/lib/auth";
import { Loading } from "@/components/ui";
import type { SystemRole } from "@/types";

interface NavItem {
  href: string;
  label: string;
  roles?: SystemRole[];
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/workflows", label: "Workflows" },
  { href: "/evaluations", label: "My runs" },
  { href: "/learning", label: "Learning" },
  { href: "/analytics", label: "Analytics", roles: ["MANAGER", "ADMIN"] },
  { href: "/governance", label: "Governance", roles: ["MANAGER", "ADMIN"] },
  { href: "/admin", label: "Admin", roles: ["ADMIN"] },
];

export function Shell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) return <Loading label="Checking your session..." />;
  if (!user) return null;

  const items = NAV.filter((item) => !item.roles || item.roles.includes(user.system_role));

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-6 py-3">
          <Link href="/dashboard" className="text-sm font-semibold">
            Enterprise AI Enablement Lab
          </Link>
          <nav className="flex flex-1 flex-wrap gap-1">
            {items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-lg px-3 py-1.5 text-sm transition ${
                    active ? "bg-brand-50 font-medium text-brand-700" : "text-muted hover:bg-canvas"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-3">
            <div className="text-right leading-tight">
              <p className="text-sm font-medium">{user.name}</p>
              <p className="text-xs text-muted">
                {user.job_role}
                {user.department_name ? ` · ${user.department_name}` : ""}
              </p>
            </div>
            <button onClick={logout} className="btn-secondary px-3 py-1.5 text-xs">
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}
