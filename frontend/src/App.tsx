/**
 * A functional harness, not the interface.
 *
 * Deliberately plain: no styling beyond default Tailwind, no motion, no
 * detail levels. It exists to prove the contract round-trips and to render
 * every message type so the next person can see what the backend actually
 * sends. The interface design comes after this.
 */

import { useEffect, useState } from "react";

import type { StepPresented } from "@shared/schema";

import { useStore } from "./store";

export default function App() {
  const store = useStore();

  // Connect once on load; the button is there for reconnecting.
  useEffect(() => {
    store.connect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-white p-6 text-sm text-gray-900">
      <header className="mb-4">
        <h1 className="text-xl font-bold">SIMBA harness</h1>
        <p className="text-gray-600">
          connection: <span className="font-mono">{store.status}</span>
          {store.statusDetail ? ` — ${store.statusDetail}` : ""}
        </p>
      </header>

      <Connection />
      <StartTask />
      <CurrentState />
      <CurrentStep />
      <Outcome />
      <Log />
    </div>
  );
}

function Connection() {
  const { wsUrl, setWsUrl, connect } = useStore();
  return (
    <section className="mb-4 flex gap-2">
      <input
        className="w-96 border p-1 font-mono"
        value={wsUrl}
        onChange={(event) => setWsUrl(event.target.value)}
        aria-label="Backend WebSocket URL"
      />
      <button className="border px-3 py-1" onClick={() => connect()}>
        Reconnect
      </button>
    </section>
  );
}

function StartTask() {
  const { startTask, cancel, task } = useStore();
  const [goal, setGoal] = useState("Register for CS-401");

  return (
    <section className="mb-4">
      <div className="flex gap-2">
        <input
          className="w-96 border p-1"
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
          aria-label="Goal"
        />
        <button className="border px-3 py-1" onClick={() => startTask(goal)}>
          Start
        </button>
        <button className="border px-3 py-1" onClick={cancel}>
          Cancel task
        </button>
      </div>
      {task ? (
        <p className="mt-2 text-gray-700">
          task.started — {task.goal} (about {task.estimated_steps} steps)
        </p>
      ) : null}
    </section>
  );
}

function CurrentState() {
  const { state, load } = useStore();
  return (
    <section className="mb-4">
      <p>
        state: <span className="font-mono">{state ?? "—"}</span>
      </p>
      {load ? (
        <p className="text-gray-700">
          load: {load.score} (level {load.level}) — {load.reason}
        </p>
      ) : null}
    </section>
  );
}

function CurrentStep() {
  const { step, respond } = useStore();
  const [values, setValues] = useState<Record<string, string>>({});

  // A new step means new fields; start them from whatever the backend sent.
  useEffect(() => {
    if (!step) return;
    const initial: Record<string, string> = {};
    for (const field of step.fields) initial[field.id] = field.value;
    setValues(initial);
  }, [step]);

  if (!step) return null;

  return (
    <section className="mb-4 border p-3">
      <p className="text-gray-600">
        step {step.step_index} of {step.step_total}
      </p>
      <p className="text-lg font-semibold">{step.instruction}</p>
      {step.detail ? <p className="text-gray-700">{step.detail}</p> : null}

      {step.fields.map((field) => (
        <div key={field.id} className="mt-2">
          <label className="block" htmlFor={`field-${field.id}`}>
            {field.label}
          </label>
          <input
            id={`field-${field.id}`}
            className="w-80 border p-1"
            type={field.type === "password" ? "password" : "text"}
            value={values[field.id] ?? ""}
            onChange={(event) =>
              setValues((current) => ({ ...current, [field.id]: event.target.value }))
            }
          />
        </div>
      ))}

      <div className="mt-3 flex gap-2">
        {step.actions.map((action) => (
          <button
            key={action.id}
            className="border px-3 py-1"
            onClick={() => respond(action.id, values)}
          >
            {action.label}
          </button>
        ))}
      </div>

      {step.requires_confirmation ? (
        <p className="mt-2 text-gray-600">nothing happens until you choose</p>
      ) : null}
    </section>
  );
}

function Outcome() {
  const { completed, failed, help, error, preview } = useStore();
  return (
    <section className="mb-4">
      {completed ? (
        <p>
          task.completed — {completed.summary} ({completed.steps_taken} steps,{" "}
          {completed.llm_calls} model calls, {completed.duration_ms} ms
          {completed.replayed ? ", replayed" : ""})
        </p>
      ) : null}
      {failed ? (
        <p>
          task.failed — {failed.reason}
          {failed.recoverable ? " (recoverable)" : ""}
        </p>
      ) : null}
      {help ? (
        <p>
          help.requested — {help.reason} {help.suggestion}
        </p>
      ) : null}
      {error ? (
        <p>
          error — {error.code}: {error.message}
        </p>
      ) : null}
      {preview ? (
        <div>
          <p>page.preview — {preview.caption}</p>
          <img
            className="max-w-lg border"
            alt={preview.caption}
            src={`data:image/png;base64,${preview.screenshot}`}
          />
        </div>
      ) : null}
    </section>
  );
}

function Log() {
  const log = useStore((state) => state.log);
  return (
    <section>
      <h2 className="mb-1 font-semibold">Messages ({log.length})</h2>
      <ol className="max-h-80 overflow-auto border p-2 font-mono text-xs">
        {log.map((entry, index) => (
          <li key={`${entry.seq}-${index}`}>
            <span className="text-gray-500">#{entry.seq}</span> {entry.type}
            {entry.note ? ` — ${entry.note}` : ""}{" "}
            <span className="text-gray-600">{summarise(entry.payload)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Keep the log readable: a base64 screenshot would drown everything else. */
function summarise(payload: unknown): string {
  const text = JSON.stringify(payload, (key, value) =>
    key === "screenshot" && typeof value === "string"
      ? `<${value.length} bytes of png>`
      : value,
  );
  return text.length > 300 ? `${text.slice(0, 300)}…` : text;
}

export type { StepPresented };
