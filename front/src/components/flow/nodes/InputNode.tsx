import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { Inbox, AlertTriangle, CheckCircle2 } from "lucide-react";
import { useMemo } from "react";
import { Textarea } from "@/components/ui/textarea";
import { useFlow, type InputNodeData } from "@/store/flowStore";

export function InputNode({ id, data, selected }: NodeProps & { data: InputNodeData }) {
  const setInputValue = useFlow((s) => s.setInputValue);

  const validity = useMemo(() => {
    const t = data.value.trim();
    if (!t) return { ok: true, kind: "empty" as const };
    try {
      JSON.parse(t);
      return { ok: true, kind: "json" as const };
    } catch (e) {
      return {
        ok: false,
        kind: "invalid" as const,
        message: e instanceof Error ? e.message : String(e),
      };
    }
  }, [data.value]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.18 }}
      className={`w-[260px] rounded-2xl border bg-white shadow-sm transition-shadow ${
        selected
          ? "border-mts-red shadow-[0_0_0_3px_rgba(255,0,50,0.12)]"
          : "border-mts-border"
      }`}
    >
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-mts-red !border-white"
      />

      <div className="flex items-center justify-between px-3 py-2 border-b border-mts-border">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-mts-ink text-white">
            <Inbox className="h-3.5 w-3.5" />
          </div>
          <div className="text-xs font-semibold text-mts-ink">{data.label}</div>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-mts-muted">
          json
        </span>
      </div>

      <div className="p-2">
        <Textarea
          value={data.value}
          onChange={(e) => setInputValue(id, e.target.value)}
          className="text-[11px] font-mono leading-[1.45] min-h-[110px] max-h-[180px] resize-y scrollbar-thin border-mts-border/70 bg-mts-surface/60 p-2 nodrag nopan"
          onMouseDownCapture={(e) => e.stopPropagation()}
          spellCheck={false}
          placeholder='{"key":"value"}'
        />
        <div className="mt-1.5 flex items-center gap-1.5 text-[10px]">
          {validity.ok ? (
            <>
              <CheckCircle2 className="h-3 w-3 text-emerald-500" />
              <span className="text-mts-muted">
                {validity.kind === "empty"
                  ? "no input (Lua input = nil)"
                  : "valid JSON · exposed as global input"}
              </span>
            </>
          ) : (
            <>
              <AlertTriangle className="h-3 w-3 text-amber-500" />
              <span className="text-amber-700">
                invalid JSON · будет передано как строка
              </span>
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
}
