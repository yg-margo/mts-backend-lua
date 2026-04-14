import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/cn";

interface OutputViewProps {
  stdout: string[];
  error?: string;
  emptyHint?: string;
  className?: string;
}

export function OutputView({
  stdout,
  error,
  emptyHint,
  className,
}: OutputViewProps) {
  const hasLines = stdout.length > 0;

  return (
    <div className={cn("text-[11px] leading-[1.5] font-mono", className)}>
      {error ? (
        <div className="flex items-start gap-2 text-red-300">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span className="whitespace-pre-wrap break-words">{error}</span>
        </div>
      ) : hasLines ? (
        <div className="space-y-0.5">
          {stdout.map((line, i) => (
            <div key={i} className="whitespace-pre-wrap break-words">
              <span className="select-none pr-2 text-white/30">
                {String(i + 1).padStart(2, " ")}
              </span>
              {line}
            </div>
          ))}
        </div>
      ) : (
        <div className="italic text-white/40">{emptyHint ?? "нет вывода"}</div>
      )}
    </div>
  );
}
