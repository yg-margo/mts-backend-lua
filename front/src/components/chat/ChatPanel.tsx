import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Message, type ApplyCodePayload } from "./Message";
import { ChatInput } from "./ChatInput";
import { ThinkingPanel } from "./ThinkingPanel";
import { hasPendingClarification, useChat } from "@/store/chatStore";
import { useFlow } from "@/store/flowStore";
import { useThinking } from "@/store/thinkingStore";
import { openGenerationStream, type WsServerEvent } from "@/lib/ws";
import type { GenerateResult } from "@/lib/api";
import { MessageSquare, Eraser } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ChatPanel() {
  const { messages, isGenerating, append, update, setGenerating, clear } =
    useChat();
  const setNodeCode = useFlow((s) => s.setNodeCode);
  const setNodeEntry = useFlow((s) => s.setNodeEntry);
  const setInputValue = useFlow((s) => s.setInputValue);
  const getLuaNode = useFlow((s) => s.getLuaNode);
  const getInputNode = useFlow((s) => s.getInputNode);
  const selectNode = useFlow((s) => s.selectNode);

  const pendingClarification = hasPendingClarification(messages);
  const inputLocked = isGenerating || pendingClarification;

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const viewport = el.querySelector<HTMLDivElement>(
      "[data-radix-scroll-area-viewport]"
    );
    if (viewport) viewport.scrollTop = viewport.scrollHeight;
  }, [messages.length, isGenerating]);

  const applyResultToNodes = (payload: ApplyCodePayload) => {
    const lua = getLuaNode();
    if (lua) {
      setNodeCode(lua.id, payload.code);
      setNodeEntry(lua.id, payload.entryPoint ?? undefined);
      selectNode(lua.id);
    }

    const inp = getInputNode();
    const hasSkeleton =
      payload.inputs != null && Object.keys(payload.inputs).length > 0;
    if (inp && hasSkeleton) {
      const skeleton = payload.inputs as Record<string, unknown>;
      let prev: Record<string, unknown> = {};
      try {
        const parsed: unknown = JSON.parse(inp.data.value || "{}");
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          prev = parsed as Record<string, unknown>;
        }
      } catch {
        // current input isn't valid JSON — fall back to fresh skeleton
      }
      const merged: Record<string, unknown> = {};
      for (const k of Object.keys(skeleton)) {
        merged[k] = Object.prototype.hasOwnProperty.call(prev, k)
          ? prev[k]
          : skeleton[k];
      }
      setInputValue(inp.id, JSON.stringify(merged, null, 2));
    }
  };

  const handleGenerateResult = (result: GenerateResult) => {
    if (result.ok === "code") {
      append({
        role: "assistant",
        content: "Готово — положил код в ноду.",
        code: result.code,
        inputs: result.inputs ?? undefined,
        entryPoint: result.entryPoint ?? undefined,
      });
      applyResultToNodes({
        code: result.code,
        inputs: result.inputs ?? undefined,
        entryPoint: result.entryPoint ?? undefined,
      });
    } else if (result.ok === "clarify") {
      append({
        role: "assistant",
        content: "Уточни пару деталей, чтобы код получился точнее:",
        clarification: {
          sessionId: result.sessionId,
          questions: result.questions,
          status: "pending",
        },
      });
    } else {
      append({
        role: "error",
        content: result.message,
        partialCode: result.partialCode || undefined,
        hint: result.hint || undefined,
      });
    }
  };

  const runStream = (
    payload: Parameters<typeof openGenerationStream>[0],
    onClarifyResult: (r: Extract<GenerateResult, { ok: "clarify" }>) => void,
    onCodeResult: (r: Extract<GenerateResult, { ok: "code" }>) => void,
    onErrorResult: (r: Extract<GenerateResult, { ok: "error" }>) => void
  ) => {
    const thinking = useThinking.getState();
    thinking.reset();
    thinking.start();
    setGenerating(true);

    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      useThinking.getState().finish();
      setGenerating(false);
    };

    const handle = (ev: WsServerEvent) => {
      const t = useThinking.getState();
      switch (ev.type) {
        case "heartbeat":
          break;
        case "stage":
          t.setStage(ev.stage, ev.cycle, ev.error);
          break;
        case "plan":
          t.appendEvent({ kind: "plan", steps: ev.steps });
          break;
        case "snippet":
          t.appendEvent({ kind: "snippet", preview: ev.preview });
          break;
        case "token":
          t.appendToken(ev.stage, ev.text, ev.cycle);
          break;
        case "stage_done":
          // nothing to render; code_delta already holds the full text
          break;
        case "validator":
          t.appendEvent({
            kind: "validator",
            success: ev.success,
            errors: ev.errors,
          });
          break;
        case "clarification":
          onClarifyResult({
            ok: "clarify",
            sessionId: ev.session_id,
            questions: ev.questions,
          });
          finish();
          break;
        case "done":
          onCodeResult({
            ok: "code",
            code: ev.code,
            inputs: ev.inputs ?? null,
            entryPoint: ev.entry_point
              ? {
                  name: ev.entry_point.name,
                  params: ev.entry_point.params,
                }
              : null,
          });
          finish();
          break;
        case "error":
          onErrorResult({
            ok: "error",
            status: 0,
            message: ev.message,
            errors: ev.errors ?? [],
            partialCode: ev.partial_code ?? "",
            hint: ev.hint ?? "",
          });
          finish();
          break;
      }
    };

    openGenerationStream(payload, {
      onEvent: handle,
      onClose: ({ clean, code, reason }) => {
        if (!settled) {
          onErrorResult({
            ok: "error",
            status: 0,
            message:
              !clean || code !== 1000
                ? `WebSocket закрылся (${code}${reason ? ": " + reason : ""})`
                : "Соединение закрылось без ответа",
            errors: [],
            partialCode: "",
            hint: "",
          });
          finish();
        }
      },
      onSocketError: () => {
        if (!settled) {
          onErrorResult({
            ok: "error",
            status: 0,
            message: "Ошибка WebSocket-соединения",
            errors: [],
            partialCode: "",
            hint: "",
          });
          finish();
        }
      },
    });
  };

  const onSubmit = (prompt: string) => {
    append({ role: "user", content: prompt });
    runStream(
      { prompt },
      handleGenerateResult,
      handleGenerateResult,
      handleGenerateResult
    );
  };

  const onSubmitClarification = (messageId: string, answers: string[]) => {
    const msg = useChat.getState().messages.find((m) => m.id === messageId);
    if (!msg?.clarification || msg.clarification.status !== "pending") return;

    const { sessionId } = msg.clarification;
    const clarification = msg.clarification;

    runStream(
      { session_id: sessionId, answers },
      handleGenerateResult,
      (result) => {
        update(messageId, {
          clarification: { ...clarification, status: "answered", answers },
        });
        handleGenerateResult(result);
      },
      (result) => {
        if (result.message.includes("expired") || result.message.includes("not found")) {
          update(messageId, {
            clarification: { ...clarification, status: "expired", answers },
          });
          append({
            role: "error",
            content: "Сессия уточнений истекла. Отправь запрос заново.",
          });
          return;
        }
        update(messageId, {
          clarification: { ...clarification, status: "answered", answers },
        });
        handleGenerateResult(result);
      }
    );
  };

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center justify-between gap-2 border-b border-mts-border px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-mts-red text-white">
            <MessageSquare className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold text-mts-ink">Chat</div>
            <div className="text-[11px] text-mts-muted">
              Genera Lua · MTS LocalScript
            </div>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={clear}
          disabled={messages.length === 0 || isGenerating}
          className="h-8 px-2 text-[12px] text-mts-muted hover:text-mts-ink"
          title="Очистить чат"
        >
          <Eraser className="h-3.5 w-3.5" />
          Очистить
        </Button>
      </div>

      <ScrollArea ref={scrollRef} className="flex-1">
        <div className="flex flex-col gap-4 p-4">
          {messages.map((m) => (
            <Message
              key={m.id}
              message={m}
              onInsertCode={applyResultToNodes}
              onSubmitClarification={onSubmitClarification}
              clarificationDisabled={isGenerating}
            />
          ))}
          <ThinkingPanel />
          {isGenerating && (
            <div className="flex items-center gap-2 text-xs text-mts-muted pl-11">
              <div className="flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-mts-red animate-bounce [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 rounded-full bg-mts-red animate-bounce [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 rounded-full bg-mts-red animate-bounce" />
              </div>
              генерирую Lua…
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="border-t border-mts-border p-3">
        <ChatInput onSubmit={onSubmit} disabled={inputLocked} />
        <div className="mt-2 text-[11px] text-mts-muted">
          {pendingClarification && !isGenerating
            ? "Ответь на вопросы выше, чтобы продолжить"
            : "Enter — отправить · Shift+Enter — новая строка"}
        </div>
      </div>
    </div>
  );
}
