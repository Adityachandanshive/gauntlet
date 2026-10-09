import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gauntlet",
  description: "Repository-specific benchmarks for coding agents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-neutral-950 text-neutral-100 antialiased">
        <header className="border-b border-neutral-800">
          <nav className="mx-auto flex max-w-6xl items-center justify-between px-8 py-4">
            <Link href="/" className="text-lg font-bold tracking-tight">Gauntlet</Link>
            <Link href="/new" className="rounded bg-emerald-500 px-4 py-2 text-sm font-medium text-black hover:bg-emerald-400">
              New benchmark
            </Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}