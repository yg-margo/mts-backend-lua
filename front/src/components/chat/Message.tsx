import { motion } from "framer-motion";
import { Copy, AlertCircle, Sparkles, User } from "lucide-react";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/store/chatStore";

interface MessageProps {
  message: ChatMessage;
  onInsertCode?: (code: string) => void;
}

export function Message({ message, onInsertCode }: MessageProps) {
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

        {message.code && (
          <CodeBlock
            code={message.code}
            label="Lua"
            onInsertCode={onInsertCode}
          />
        )}

        {message.partialCode && (
          <CodeBlock
            code={message.partialCode}
            label="partial"
            tone="error"
            onInsertCode={onInsertCode}
          />
        )}

        {message.hint && (
          <div className="mt-2 text-xs italic opacity-80">{message.hint}</div>
        )}
      </div>
    </motion.div>
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
  onInsertCode?: (code: string) => void;
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
              onClick={() => onInsertCode(code)}
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
