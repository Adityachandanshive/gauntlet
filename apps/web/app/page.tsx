"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import Leaderboard from "@/components/Leaderboard";
import TaskTable from "@/components/TaskTable";
import type { Row, Task } from "@/lib/types";

export default function Home() {
  const [rows, setRows] = useState<Row[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([get<Row[]>("/api/leaderboard"), get<Task[]>("/api/tasks")])
      .then(([l, t]) => { setRows(l); setTasks(t); })
      .catch((e) => setErr(String(e.message ?? e)));
  }, []);

  const accepted = tasks.filter((t) => t.status === "accepted").length;

  return (
    <main className="mx-auto max-w-6xl p-8">
      <section className="py-8">
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight">
          Which coding agent works best on <span className="text-emerald-400">your</span> codebase?
        </h1>
        <p className="mt-3 max-w-2xl text-neutral-400">
          Gauntlet turns a GitHub repository into validated bug-fixing tasks, runs coding agents
          on them in isolated sandboxes, and reports solve rate, time and cost.
        </p>
        <Link href="/new" className="mt-6 inline-block rounded bg-emerald-500 px-5 py-3 font-medium text-black hover:bg-emerald-400">
          Run a benchmark
        </Link>
      </section>

      {err && (
        <p className="mb-6 rounded bg-red-950 p-3 text-red-300">
          Cannot reach the API ({err}). Is uvicorn running on port 8000?
        </p>
      )}

      <h2 className="text-xl font-semibold">Leaderboard (all runs)</h2>
      <div className="mt-3"><Leaderboard rows={rows} /></div>

      <h2 className="mt-10 text-xl font-semibold">
        Tasks{" "}
        <span className="text-sm font-normal text-neutral-400">
          ({accepted} accepted, {tasks.length - accepted} rejected)
        </span>
      </h2>
      <div className="mt-3">
        <TaskTable tasks={tasks} models={rows.map((r) => r.model)} />
      </div>
    </main>
  );
}