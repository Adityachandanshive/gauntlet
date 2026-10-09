"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { get, MODEL_LABEL } from "@/lib/api";
import Leaderboard from "@/components/Leaderboard";
import TaskTable from "@/components/TaskTable";
import type { Run } from "@/lib/types";

const STEPS = [
  { key: "queued", label: "Queued" },
  { key: "generating", label: "Generate & validate tasks" },
  { key: "solving", label: "Agents solving" },
  { key: "done", label: "Report ready" },
];

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const d = await get<Run>(`/api/benchmarks/${id}`);
        if (stop) return;
        setRun(d);
        setErr("");
        if (d.status === "done" || d.status === "failed") return;
      } catch (e) {
        if (!stop) setErr((e as Error).message);
      }
      timer = setTimeout(tick, 3000);
    };
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, [id]);

  const idx = run ? STEPS.findIndex((s) => s.key === run.status) : 0;
  const failed = run?.status === "failed";
  const accepted = run?.tasks.filter((t) => t.status === "accepted").length ?? 0;
  const rejected = (run?.tasks.length ?? 0) - accepted;

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">Benchmark report</h1>
          {run?.request && <p className="mt-1 text-neutral-400">{run.request.repo}</p>}
        </div>
        <button
          onClick={() => { navigator.clipboard.writeText(window.location.href); setCopied(true); }}
          className="rounded border border-neutral-700 px-4 py-2 text-sm hover:bg-neutral-900">
          {copied ? "Link copied" : "Copy report link"}
        </button>
      </div>

      {err && <p className="mt-4 rounded bg-red-950 p-3 text-red-300">{err}</p>}

      <ol className="mt-8 grid gap-3 sm:grid-cols-4">
        {STEPS.map((s, i) => {
          const state = failed ? (i < idx ? "done" : "todo") : i < idx ? "done" : i === idx ? "active" : "todo";
          return (
            <li key={s.key}
                className={`rounded border p-3 text-sm ${
                  state === "done" ? "border-emerald-700 text-emerald-300"
                  : state === "active" ? "border-sky-500 text-sky-300"
                  : "border-neutral-800 text-neutral-500"}`}>
              {s.label}
            </li>
          );
        })}
      </ol>

      {run?.status === "generating" && (
        <p className="mt-4 text-neutral-400">
          Generating bugs and validating each one in a sandbox. {run.tasks.length} candidates checked so far
          ({accepted} accepted, {rejected} rejected).
        </p>
      )}
      {run?.status === "solving" && (
        <p className="mt-4 text-neutral-400">
          Running {MODEL_LABEL[run.model ?? ""] ?? run.model} on {run.n_tasks} validated tasks…
        </p>
      )}
      {failed && (
        <p className="mt-4 rounded bg-red-950 p-3 text-red-300">Run failed: {run?.error}</p>
      )}

      <h2 className="mt-10 text-xl font-semibold">Leaderboard</h2>
      <div className="mt-3"><Leaderboard rows={run?.leaderboard ?? []} /></div>

      <h2 className="mt-10 text-xl font-semibold">
        Tasks <span className="text-sm font-normal text-neutral-400">({accepted} accepted, {rejected} rejected)</span>
      </h2>
      <div className="mt-3">
        <TaskTable tasks={run?.tasks ?? []} models={run?.leaderboard.map((r) => r.model) ?? []} />
      </div>

      {run?.log && (
        <details className="mt-10">
          <summary className="cursor-pointer text-neutral-400">Run log</summary>
          <pre className="mt-2 max-h-80 overflow-auto rounded bg-neutral-900 p-4 text-xs">{run.log}</pre>
        </details>
      )}
    </main>
  );
}