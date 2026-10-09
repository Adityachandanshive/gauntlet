"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { post } from "@/lib/api";

const MODELS = [
  { id: "MODEL_CHEAP", label: "Nemotron 3 Nano", note: "cheaper, more attempts needed" },
  { id: "MODEL_SOLVER", label: "Nemotron 3 Super", note: "stronger, higher cost" },
];

export default function NewBenchmark() {
  const router = useRouter();
  const [repo, setRepo] = useState("");
  const [models, setModels] = useState<string[]>(["MODEL_CHEAP", "MODEL_SOLVER"]);
  const [attempts, setAttempts] = useState(2);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const toggle = (id: string) =>
    setModels((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!models.length) { setErr("Select at least one model."); return; }
    setBusy(true);
    try {
      const { id } = await post<{ id: string }>("/api/benchmarks", { repo: repo.trim(), models, attempts });
      router.push(`/runs/${id}`);
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-bold">New benchmark</h1>
      <p className="mt-2 text-neutral-400">
        Paste a public GitHub repository. Gauntlet generates bugs, validates them, and compares agents.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-6">
        <div>
          <label className="block text-sm font-medium">Repository URL</label>
          <input
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="https://github.com/mahmoud/boltons"
            required
            className="mt-2 w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 outline-none focus:border-emerald-500"
          />
          <button type="button" onClick={() => setRepo("https://github.com/mahmoud/boltons")}
                  className="mt-2 text-sm text-sky-400 hover:underline">
            Use example: boltons
          </button>
        </div>

        <div>
          <span className="block text-sm font-medium">Agents to compare</span>
          <div className="mt-2 space-y-2">
            {MODELS.map((m) => (
              <label key={m.id} className="flex items-center gap-3 rounded border border-neutral-800 p-3">
                <input type="checkbox" checked={models.includes(m.id)} onChange={() => toggle(m.id)} />
                <span className="font-medium">{m.label}</span>
                <span className="text-sm text-neutral-500">{m.note}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium">Attempts per task</label>
          <select value={attempts} onChange={(e) => setAttempts(Number(e.target.value))}
                  className="mt-2 rounded border border-neutral-700 bg-neutral-900 px-3 py-2">
            {[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>

        <p className="rounded bg-neutral-900 p-3 text-sm text-neutral-400">
          Works best with small pure-Python repos whose pytest suite passes quickly. A run can take
          20+ minutes and uses model credits.
        </p>

        {err && <p className="rounded bg-red-950 p-3 text-red-300">{err}</p>}

        <button disabled={busy}
                className="rounded bg-emerald-500 px-5 py-3 font-medium text-black hover:bg-emerald-400 disabled:opacity-50">
          {busy ? "Starting…" : "Start benchmark"}
        </button>
      </form>
    </main>
  );
}