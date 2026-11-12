/**
 * The bundled backend, for the installed app only (2026-11-13).
 *
 * In development the backend is started by `run.ps1` (or by hand) and this
 * file is never used: `main.ts` calls into it only when `app.isPackaged`.
 *
 * In the installed app there is nobody to start the backend, so the host does:
 * the Windows embeddable Python and the backend's code are shipped under
 * `resources/backend/` (`tools/build_installer.py`), and this spawns
 *
 *     python -m uvicorn backend.orchestrator.app:app --host 127.0.0.1 --port <port>
 *
 * with `SIMBA_BROWSER=electron`, keeps the one PID it got, and stops exactly
 * that PID — and the processes it started, which is Playwright's driver — when
 * the host quits. Nothing is matched by name or pattern (CLAUDE.md).
 *
 * Ports. In development CDP is 9222 and the backend 8000, as always. Installed,
 * both are chosen fresh on every launch, on 127.0.0.1 only:
 *
 *   CDP      Chromium is given `--remote-debugging-port=0`, picks a free port
 *            itself, and writes it to `DevToolsActivePort` in the profile
 *            folder; read from there. No window between choosing and binding.
 *   backend  a port the OS hands out to a throwaway listener, closed and passed
 *            to uvicorn. The overlay is told it with `?ws=` on its own URL,
 *            which `src/connection.ts` already reads — no contract change.
 *
 * Writable data. The install folder is the program, not a place to keep a
 * person's things, so every file the backend writes goes under the profile
 * folder instead (`dataEnvironment` below lists them all).
 */

import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import path from "node:path";

/** Where the build script puts the bundle, inside the app's `resources`. */
export function bundleDir(resourcesPath: string): string {
  return path.join(resourcesPath, "backend");
}

/** A port nothing is listening on right now, on 127.0.0.1. */
export function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => (port > 0 ? resolve(port) : reject(new Error("no free port"))));
    });
  });
}

/** The file Chromium names its chosen debugging port in, given port 0. */
export function devToolsPortFile(userData: string): string {
  return path.join(userData, "DevToolsActivePort");
}

/**
 * The CDP port Chromium chose. The file is removed before the app is ready
 * (`main.ts`), so a port read here is this launch's, never the last one's.
 */
export async function devToolsPort(userData: string, limitMs = 15_000): Promise<number> {
  const file = devToolsPortFile(userData);
  const until = Date.now() + limitMs;
  while (Date.now() < until) {
    try {
      const first = fs.readFileSync(file, "utf8").split(/\r?\n/)[0]?.trim() ?? "";
      const port = Number(first);
      if (Number.isInteger(port) && port > 0) return port;
    } catch {
      // Not written yet.
    }
    await new Promise((done) => setTimeout(done, 100));
  }
  throw new Error(`Chromium did not write ${file} within ${limitMs} ms`);
}

/**
 * Every path the backend would otherwise write inside the install folder,
 * moved into the profile folder. Each variable is one the backend reads:
 *
 *   SIMBA_TILES        data/tiles.json      the home screen's tiles
 *   SIMBA_VAULT        data/vault.json      sign-in details, DPAPI-encrypted
 *   SIMBA_ROUTINES     data/routines.json   routines a helper showed
 *   SIMBA_TRACE_DB     data/traces.db       trace memory
 *   SIMBA_STEPS        data/steps.jsonl     channel B's step rows
 *   SIMBA_LOG_FILE     logs/backend.log     the run log
 *   SIMBA_LLM_LOG_DIR  logs/                the model's prompt transcripts
 */
export function dataEnvironment(userData: string): Record<string, string> {
  const data = path.join(userData, "data");
  const logs = path.join(userData, "logs");
  return {
    SIMBA_TILES: path.join(data, "tiles.json"),
    SIMBA_VAULT: path.join(data, "vault.json"),
    SIMBA_ROUTINES: path.join(data, "routines.json"),
    SIMBA_TRACE_DB: path.join(data, "traces.db"),
    SIMBA_STEPS: path.join(data, "steps.jsonl"),
    SIMBA_LOG_FILE: path.join(logs, "backend.log"),
    SIMBA_LLM_LOG_DIR: logs,
  };
}

export interface Bundled {
  child: ChildProcess;
  pid: number;
  port: number;
  cdpPort: number;
  ws: string;
}

/** Start the bundled backend. Resolves once it has a PID, not once it is up. */
export function startBundled(options: {
  resourcesPath: string;
  userData: string;
  cdpPort: number;
  port: number;
  startUrl: string;
}): Bundled {
  const root = bundleDir(options.resourcesPath);
  const python = path.join(root, "python", "python.exe");
  const code = path.join(root, "app");
  const logs = path.join(options.userData, "logs");
  fs.mkdirSync(path.join(options.userData, "data"), { recursive: true });
  fs.mkdirSync(logs, { recursive: true });

  // The backend's own console, for when it dies before its log is set up.
  const out = fs.openSync(path.join(logs, "backend-console.log"), "a");
  const child = spawn(
    python,
    ["-m", "uvicorn", "backend.orchestrator.app:app",
      "--host", "127.0.0.1", "--port", String(options.port)],
    {
      cwd: code,
      windowsHide: true,
      stdio: ["ignore", out, out],
      env: {
        ...process.env,
        ...dataEnvironment(options.userData),
        SIMBA_BROWSER: "electron",
        SIMBA_CDP_URL: `http://127.0.0.1:${options.cdpPort}`,
        SIMBA_START_URL: options.startUrl,
        PYTHONUTF8: "1",
      },
    },
  );
  fs.closeSync(out);
  if (child.pid === undefined) throw new Error(`could not start ${python}`);
  return {
    child,
    pid: child.pid,
    port: options.port,
    cdpPort: options.cdpPort,
    ws: `ws://127.0.0.1:${options.port}/ws`,
  };
}

/** Whether the backend has already gone, by exit or by signal. */
export function exited(bundled: Bundled): boolean {
  return bundled.child.exitCode !== null || bundled.child.signalCode !== null;
}

/** Wait until the backend answers on `/`, or it exits, or time runs out. */
export async function waitUntilUp(bundled: Bundled, limitMs = 60_000): Promise<boolean> {
  const until = Date.now() + limitMs;
  while (Date.now() < until) {
    if (exited(bundled)) return false;
    const answered = await new Promise<boolean>((resolve) => {
      const request = http.get(
        { host: "127.0.0.1", port: bundled.port, path: "/", timeout: 1000 },
        (response) => {
          response.resume();
          resolve(true);
        },
      );
      request.on("error", () => resolve(false));
      request.on("timeout", () => {
        request.destroy();
        resolve(false);
      });
    });
    if (answered) return true;
    await new Promise((done) => setTimeout(done, 150));
  }
  return false;
}

/**
 * Stop the backend this host started, and what it started, by its PID.
 *
 * `taskkill /PID <pid> /T /F` reaches that one process and its descendants
 * (Playwright's driver, `node.exe`, which does not outlive its parent reliably
 * on its own). No image name, no filter — the same form `run.ps1` uses.
 */
export function stopBundled(bundled: Bundled): void {
  if (exited(bundled)) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/PID", String(bundled.pid), "/T", "/F"], { windowsHide: true });
  } else {
    bundled.child.kill();
  }
}
