"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";
import { ErrorBox } from "@/components/ui";

const DEMO_ACCOUNTS = [
  { email: "employee@demo.com", label: "Employee", detail: "Developer, Engineering" },
  { email: "manager@demo.com", label: "Manager", detail: "Engineering department view" },
  { email: "admin@demo.com", label: "Admin", detail: "Full organisation view" },
];

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("employee@demo.com");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <h1 className="text-xl font-semibold">Enterprise AI Enablement Lab</h1>
        <p className="mt-2 text-sm text-muted">
          Acme Corp&apos;s internal platform for approved AI workflows, evaluation and adoption
          reporting.
        </p>

        <form onSubmit={handleSubmit} className="card mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="label">
              Email
            </label>
            <input
              id="email"
              type="email"
              className="input mt-1"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <div>
            <label htmlFor="password" className="label">
              Password
            </label>
            <input
              id="password"
              type="password"
              className="input mt-1"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          {error && <ErrorBox message={error} />}
          <button type="submit" className="btn-primary w-full" disabled={submitting}>
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div className="card mt-4">
          <p className="label">Demo accounts</p>
          <ul className="mt-3 space-y-2">
            {DEMO_ACCOUNTS.map((account) => (
              <li key={account.email}>
                <button
                  type="button"
                  onClick={() => {
                    setEmail(account.email);
                    setPassword("demo1234");
                  }}
                  className="flex w-full items-center justify-between rounded-lg border border-line px-3 py-2 text-left text-sm hover:bg-canvas"
                >
                  <span>
                    <span className="font-medium">{account.label}</span>
                    <span className="block text-xs text-muted">{account.detail}</span>
                  </span>
                  <span className="font-mono text-xs text-muted">{account.email}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">
            Password for every demo account: <span className="font-mono">demo1234</span>. All
            people, workflows and history in this instance are synthetic.
          </p>
        </div>
      </div>
    </div>
  );
}
