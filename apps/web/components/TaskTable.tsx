import Link from "next/link";
import { MODEL_LABEL } from "@/lib/api";
import type { Task } from "@/lib/types";

export default function TaskTable({ tasks, models }: { tasks: Task[]; models: string[] }) {
  if (!tasks.length) return <p className="text-neutral-500">No tasks yet.</p>;
  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-800">
      <table className="w-full text-sm">
        <thead className="bg-neutral-900 text-left text-neutral-400">
          <tr>
            <th className="px-4 py-3 font-medium">Task</th>
            <th className="px-4 py-3 font-medium">Validation</th>
            <th className="px-4 py-3 font-medium">Repeatability</th>
            {models.map((m) => (
              <th key={m} className="px-4 py-3 font-medium">{MODEL_LABEL[m] ?? m}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => (
            <tr key={t.id} className="border-t border-neutral-800">
              <td className="px-4 py-3">
                <Link className="text-sky-400 hover:underline" href={`/tasks/${t.id}`}>{t.id}</Link>
                {t.file && <div className="text-xs text-neutral-500">{t.file}</div>}
              </td>
              <td className="px-4 py-3">
                <span className={t.status === "accepted" ? "text-emerald-400" : "text-amber-400"}>
                  {t.status}
                </span>
                {t.reasons[0] && (
                  <div className="max-w-xs truncate text-xs text-neutral-500">{t.reasons[0]}</div>
                )}
              </td>
              <td className="px-4 py-3">{t.repeatability ?? "–"}</td>
              {models.map((m) => {
                const x = t.results[m];
                return <td key={m} className="px-4 py-3">{x ? `${x.solved}/${x.attempts}` : "–"}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}