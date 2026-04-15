export type WsStage =
  | "clarifier"
  | "planner"
  | "coder"
  | "validator"
  | "fixer";

export interface WsValidatorError {
  line: number | null;
  message: string;
}

export type WsServerEvent =
  | { type: "heartbeat"; t?: number }
  | { type: "stage"; stage: WsStage; cycle?: number; error?: string; final?: boolean }
  | { type: "stage_done"; stage: "coder" | "fixer"; code?: string; cycle?: number }
  | { type: "plan"; steps: string[] }
  | {
      type: "token";
      stage: "coder" | "fixer";
      text: string;
      cycle?: number;
    }
  | { type: "validator"; success: boolean; errors: WsValidatorError[] }
  | {
      type: "clarification";
      session_id: string;
      questions: string[];
      chat_session_id?: string;
    }
  | {
      type: "done";
      code: string;
      inputs: Record<string, unknown> | null;
      entry_point: { name: string; params: string[] } | null;
      chat_session_id?: string;
    }
  | {
      type: "error";
      message: string;
      errors?: WsValidatorError[];
      partial_code?: string;
      hint?: string;
    };

export interface WsHandlers {
  onEvent?: (event: WsServerEvent) => void;
  onClose?: (info: { clean: boolean; code: number; reason: string }) => void;
  onSocketError?: (err: Event) => void;
}

export type WsInitialPayload =
  | { prompt: string; chat_session_id?: string }
  | { session_id: string; answers: string[]; chat_session_id?: string };

function resolveWsUrl(): string {
  const base =
    (import.meta as unknown as { env: Record<string, string> }).env
      ?.VITE_API_URL ?? "";
  if (!base) {
    const loc = window.location;
    const proto = loc.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${loc.host}/generate/ws`;
  }
  const httpUrl = new URL(base);
  const wsProto = httpUrl.protocol === "https:" ? "wss:" : "ws:";
  return `${wsProto}//${httpUrl.host}/generate/ws`;
}

export function openGenerationStream(
  payload: WsInitialPayload,
  handlers: WsHandlers = {}
): () => void {
  const ws = new WebSocket(resolveWsUrl());

  ws.addEventListener("open", () => {
    ws.send(JSON.stringify(payload));
  });

  ws.addEventListener("message", (e) => {
    let parsed: WsServerEvent | null = null;
    try {
      parsed = JSON.parse(e.data) as WsServerEvent;
    } catch {
      handlers.onEvent?.({
        type: "error",
        message: "malformed event from server",
      });
      return;
    }
    handlers.onEvent?.(parsed);
  });

  ws.addEventListener("error", (err) => {
    handlers.onSocketError?.(err);
  });

  ws.addEventListener("close", (e) => {
    handlers.onClose?.({ clean: e.wasClean, code: e.code, reason: e.reason });
  });

  return () => {
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
  };
}
