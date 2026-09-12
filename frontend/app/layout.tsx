import type { Metadata } from "next";

import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Enterprise AI Enablement Lab",
  description:
    "Role-based AI workflows, automated and human evaluation, responsible-AI controls and adoption analytics.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
