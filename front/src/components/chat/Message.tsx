import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertCircle,
  CheckCircle2,
  Copy,
  HelpCircle,
  Loader2,
  Send,
  Sparkles,
  User,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import type { ChatMessage, ClarificationState } from "@/store/chatStore";

export interface ApplyCodePayload {
  code: string;
  inputs?: Record<string, unknown>;
  entryPoint?: { name: string; params: string[] };
}

interface MessageProps {
  message: ChatMessage;
  onInsertCode?: (payload: ApplyCodePayload) => void;
  onSubmitClarification?: (messageId: string, answers: string[]) => void;
  clarificationDisabled?: boolean;
}

export function Message({
  message,
  onInsertCode,
  onSubmitClarification,
  clarificationDisabled,
}: MessageProps) {
  const isUser = message.role === "user";
  const isError = message.role === "error";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className={cn(
        "flex gap-3 items-start",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
          isUser && "bg-mts-red text-white border-mts-red",
          !isUser && !isError && "bg-white text-mts-ink border-mts-border",
          isError && "bg-red-50 text-red-600 border-red-200"
        )}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : isError ? (
          <AlertCircle className="h-4 w-4" />
        ) : (
          <Sparkles className="h-4 w-4" />
        )}
      </div>

      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm shadow-sm",
          isUser && "bg-mts-red text-white rounded-tr-sm",
          !isUser && !isError && "bg-white border border-mts-border rounded-tl-sm",
          isError && "bg-red-50 border border-red-200 text-red-800 rounded-tl-sm"
        )}
      >
        <div className="whitespace-pre-wrap leading-relaxed">{message.content}</div>

        {message.clarification && onSubmitClarification && (
          <ClarificationBlock
            clarification={message.clarification}
            disabled={!!clarificationDisabled}
            onSubmit={(answers) =>
              onSubmitClarification(message.id, answers)
            }
          />
        )}

        {message.code && (
          <CodeBlock
            code={message.code}
            label="Lua"
            onInsertCode={
              onInsertCode
                ? () =>
                    onInsertCode({
                      code: message.code!,
                      inputs: message.inputs,
                      entryPoint: message.entryPoint,
                    })
                : undefined
            }
          />
        )}

        {message.partialCode && (
          <CodeBlock
            code={message.partialCode}
            label="partial"
            tone="error"
            onInsertCode={
              onInsertCode
                ? () => onInsertCode({ code: message.partialCode! })
                : undefined
            }
          />
        )}

        {message.hint && (
          <div className="mt-2 text-xs italic opacity-80">{message.hint}</div>
        )}
      </div>
    </motion.div>
  );
}

function ClarificationBlock({
  clarification,
  disabled,
  onSubmit,
}: {
  clarification: ClarificationState;
  disabled: boolean;
  onSubmit: (answers: string[]) => void;
}) {
  const [values, setValues] = useState<string[]>(() =>
    clarification.questions.map(() => "")
  );
  const inputRefs = useRef<Array<HTMLInputElement | null>>([]);

  // Autofocus the first input once when the form first renders in pending state.
  const firstRenderRef = useRef(true);
  useEffect(() => {
    if (clarification.status !== "pending") return;
    if (!firstRenderRef.current) return;
    firstRenderRef.current = false;
    inputRefs.current[0]?.focus();
  }, [clarification.status]);

  if (clarification.status === "expired") {
    return (
      <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800">
        Сессия уточнений истекла. Отправь запрос заново.
      </div>
    );
  }

  if (clarification.status === "answered") {
    const answers = clarification.answers ?? [];
    return (
      <div className="mt-3 overflow-hidden rounded-xl border border-mts-border bg-mts-surface">
        {clarification.questions.map((q, i) => (
          <div
            key={i}
            className={cn(
              "flex items-start gap-2 px-3 py-2 text-[12px]",
              i > 0 && "border-t border-mts-border/60"
            )}
          >
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
            <div className="flex-1 min-w-0">
              <div className="text-mts-muted leading-snug">{q}</div>
              <div className="mt-0.5 break-words text-mts-ink">
                {answers[i] || <span className="italic opacity-60">—</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  // pending
  const allFilled = values.every((v) => v.trim().length > 0);

  const submit = () => {
    if (!allFilled || disabled) return;
    onSubmit(values.map((v) => v.trim()));
  };

  const onKeyDown =
    (i: number) => (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      const next = inputRefs.current[i + 1];
      if (next) {
        next.focus();
      } else {
        submit();
      }
    };

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-mts-border bg-white">
      <div className="flex items-center gap-1.5 border-b border-mts-border bg-mts-surface px-3 py-1.5 text-[11px] uppercase tracking-wide text-mts-muted">
        <HelpCircle className="h-3 w-3 text-mts-red" />
        <span className="font-medium">Нужно уточнить</span>
      </div>
      <div className="space-y-2.5 p-3">
        {clarification.questions.map((q, i) => (
          <div key={i} className="space-y-1">
            <label className="block text-[12px] font-medium leading-snug text-mts-ink">
              <span className="mr-1.5 text-mts-red">{i + 1}.</span>
              {q}
            </label>
            <input
              ref={(el) => {
                inputRefs.current[i] = el;
              }}
              type="text"
              value={values[i]}
              onChange={(e) => {
                const next = [...values];
                next[i] = e.target.value;
                setValues(next);
              }}
              onKeyDown={onKeyDown(i)}
              placeholder="Твой ответ…"
              disabled={disabled}
              className="w-full rounded-lg border border-mts-border bg-white px-2.5 py-1.5 text-[12px] text-mts-ink placeholder:text-mts-muted/70 focus:border-mts-red/50 focus:outline-none focus:ring-2 focus:ring-mts-red/20 disabled:opacity-60"
            />
          </div>
        ))}
        <Button
          onClick={submit}
          disabled={!allFilled || disabled}
          size="sm"
          className="h-8 w-full rounded-lg"
        >
          {disabled ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
          Уточнить
        </Button>
      </div>
    </div>
  );
}

function CodeBlock({
  code,
  label,
  tone = "default",
  onInsertCode,
}: {
  code: string;
  label: string;
  tone?: "default" | "error";
  onInsertCode?: () => void;
}) {
  return (
    <div
      className={cn(
        "mt-3 rounded-xl border overflow-hidden",
        tone === "error"
          ? "border-red-200 bg-red-50/60"
          : "border-mts-border bg-mts-surface"
      )}
    >
      <div
        className={cn(
          "flex items-center justify-between px-3 py-1.5 text-[11px] uppercase tracking-wide",
          tone === "error" ? "text-red-700" : "text-mts-muted"
        )}
      >
        <span className="font-medium">{label}</span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[11px] text-mts-ink"
            onClick={() => navigator.clipboard.writeText(code)}
          >
            <Copy className="h-3 w-3" />
            Copy
          </Button>
          {onInsertCode && (
            <Button
              variant="default"
              size="sm"
              className="h-6 px-2 text-[11px]"
              onClick={onInsertCode}
            >
              Use in node
            </Button>
          )}
        </div>
      </div>
      <pre className="text-xs leading-5 text-mts-ink font-mono overflow-x-auto px-3 py-2.5 scrollbar-thin">
        {code}
      </pre>
    </div>
  );
}
