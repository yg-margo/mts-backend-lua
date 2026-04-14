import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { Terminal, AlertCircle, Clock } from "lucide-react";
import type { OutputNodeData } from "@/store/flowStore";

export function OutputNode({ data, selected }: NodeProps & { data: OutputNodeData }) {
  const hasLines = data.stdout.length > 0;
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.18 }}
      className={`w-[300px] rounded-2xl border bg-mts-ink text-white shadow-sm ${
        selected ? "ring-2 ring-mts-red ring-offset-2 ring-offset-white" : ""
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-mts-red !border-white"
      />

      <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-white/10">
            <Terminal className="h-3.5 w-3.5" />
          </div>
          <div className="text-xs font-semibold">{data.label}</div>
        </div>
        {typeof data.durationMs === "number" && (
          <span className="flex items-center gap-1 text-[10px] text-white/60">
            <Clock className="h-3 w-3" />
            {data.durationMs}ms
          </span>
        )}
      </div>

      <div className="px-3 py-2 text-[11px] leading-[1.5] font-mono max-h-[180px] overflow-auto scrollbar-thin">
        {data.error ? (
          <div className="flex items-start gap-2 text-red-300">
            <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <span className="whitespace-pre-wrap break-words">{data.error}</span>
          </div>
        ) : hasLines ? (
          <div className="space-y-0.5">
            {data.stdout.map((line, i) => (
              <div key={i} className="whitespace-pre-wrap break-words">
                <span className="text-white/30 select-none pr-2">
                  {String(i + 1).padStart(2, " ")}
                </span>
                {line}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-white/40 italic">
            нет вывода · нажми Run на ноде слева
          </div>
        )}
      </div>
    </motion.div>
  );
}
