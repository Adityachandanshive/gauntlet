import { MODEL_LABEL, pct } from "@/lib/api";
import type { Row } from "@/lib/types";

function Bar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 rounded bg-neutral-800">
        <div className="h-2 rounded bg-emerald-500" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span>{pct(value)}</span>
    </div>
  );
}

export default function Leaderboard({ rows }: { rows: Row[] }) {
  if (!rows.length) return <p className="text-neutral-500">No results yet.</p>;
  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-800">
      <table className="w-full text-sm">
        <thead className="bg-neutral-900 text-left text-neutral-400">
          <tr>
            {["Model", "Tasks", "Pass@1", "Pass@2", "Median s", "Avg tokens", "Cost / solved"].map((h) => (
              <th key={h} className="px-4 py-3 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.model} className="border-t border-neutral-800">
              <td className="px-4 py-3 font-medium">{MODEL_LABEL[r.model] ?? r.model}</td>
              <td className="px-4 py-3">{r.tasks}</td>
              <td className="px-4 py-3"><Bar value={r.pass_at_1} /></td>
              <td className="px-4 py-3"><Bar value={r.pass_at_2} /></td>
              <td className="px-4 py-3">{r.median_seconds?.toFixed(1) ?? "–"}</td>
              <td className="px-4 py-3">{Math.round(r.avg_tokens).toLocaleString()}</td>
              <td className="px-4 py-3">{r.cost_per_solved == null ? "–" : `$${r.cost_per_solved}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}