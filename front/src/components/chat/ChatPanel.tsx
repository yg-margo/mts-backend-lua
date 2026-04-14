import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Message } from "./Message";
import { ChatInput } from "./ChatInput";
import { useChat } from "@/store/chatStore";
import { useFlow } from "@/store/flowStore";
import { generateCode } from "@/lib/api";
import { MessageSquare, Eraser } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ChatPanel() {
  const { messages, isGenerating, append, setGenerating, clear } = useChat();
  const setNodeCode = useFlow((s) => s.setNodeCode);
  const getLuaNode = useFlow((s) => s.getLuaNode);
  const selectNode = useFlow((s) => s.selectNode);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const viewport = el.querySelector<HTMLDivElement>(
      "[data-radix-scroll-area-viewport]"
    );
    if (viewport) viewport.scrollTop = viewport.scrollHeight;
  }, [messages.length, isGenerating]);

  const applyCodeToNode = (code: string) => {
    const n = getLuaNode();
    if (!n) return;
    setNodeCode(n.id, code);
    selectNode(n.id);
  };

  const onSubmit = async (prompt: string) => {
    append({ role: "user", content: prompt });
    setGenerating(true);
    try {
      const result = await generateCode(prompt);
      if (result.ok) {
        append({
          role: "assistant",
          content: "Готово — положил код в ноду.",
          code: result.code,
        });
        applyCodeToNode(result.code);
      } else {
        append({
          role: "error",
          content: result.message,
          partialCode: result.partialCode || undefined,
          hint: result.hint || undefined,
        });
      }
    } catch (e) {
      append({
        role: "error",
        content:
          e instanceof Error
            ? `Сеть/сервер: ${e.message}`
            : "Не удалось связаться с сервером /generate",
      });
    } finally {
      setGenerating(false);
    }
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
            <Message key={m.id} message={m} onInsertCode={applyCodeToNode} />
          ))}
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
        <ChatInput onSubmit={onSubmit} disabled={isGenerating} />
        <div className="mt-2 text-[11px] text-mts-muted">
          Enter — отправить · Shift+Enter — новая строка
        </div>
      </div>
    </div>
  );
}
