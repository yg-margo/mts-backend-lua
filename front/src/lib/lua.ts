import type { LuaEngine, LuaFactory as LuaFactoryType } from "wasmoon";

export interface LuaResult {
  stdout: string[];
  error?: string;
  durationMs: number;
}

let factoryPromise: Promise<LuaFactoryType> | null = null;

async function getFactory(): Promise<LuaFactoryType> {
  if (!factoryPromise) {
    factoryPromise = import("wasmoon").then((m) => new m.LuaFactory());
  }
  return factoryPromise;
}

export interface RunLuaOptions {
  input?: unknown;
  timeoutMs?: number;
}

export async function runLua(
  code: string,
  options: RunLuaOptions = {}
): Promise<LuaResult> {
  const { input, timeoutMs = 3000 } = options;
  const started = performance.now();
  const stdout: string[] = [];
  let engine: LuaEngine | null = null;
  try {
    const factory = await getFactory();
    engine = await factory.createEngine();
    if (input !== undefined) {
      engine.global.set("input", input);
    }
    engine.global.set("print", (...args: unknown[]) => {
      stdout.push(
        args
          .map((a) => {
            if (a === null || a === undefined) return "nil";
            if (typeof a === "object") {
              try {
                return JSON.stringify(a);
              } catch {
                return String(a);
              }
            }
            return String(a);
          })
          .join("\t")
      );
    });

    const exec = engine.doString(code);
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(
        () => reject(new Error(`Execution timed out after ${timeoutMs}ms`)),
        timeoutMs
      )
    );

    await Promise.race([exec, timeout]);
    return { stdout, durationMs: Math.round(performance.now() - started) };
  } catch (err) {
    return {
      stdout,
      error: err instanceof Error ? err.message : String(err),
      durationMs: Math.round(performance.now() - started),
    };
  } finally {
    try {
      engine?.global.close();
    } catch {
      /* ignore */
    }
  }
}
