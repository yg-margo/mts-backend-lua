import { useState, type KeyboardEvent } from "react";
import { Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ChatInputProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  const submit = () => {
    const t = value.trim();
    if (!t || disabled) return;
    onSubmit(t);
    setValue("");
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex items-end gap-2 rounded-2xl border border-mts-border bg-white p-2 shadow-sm focus-within:border-mts-red/50 focus-within:ring-2 focus-within:ring-mts-red/20 transition">
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKey}
        placeholder="Опиши, что должна делать нода на Lua…"
        rows={2}
        className="border-0 focus-visible:ring-0 focus-visible:border-0 shadow-none px-2 py-1.5 min-h-[44px] max-h-40"
        disabled={disabled}
      />
      <Button
        onClick={submit}
        disabled={disabled || !value.trim()}
        size="icon"
        className="h-10 w-10 shrink-0 rounded-xl"
      >
        {disabled ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
      </Button>
    </div>
  );
}
