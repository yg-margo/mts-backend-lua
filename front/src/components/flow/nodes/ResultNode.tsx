import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { FileCode2, ArrowRightCircle, X, Copy, Check } from "lucide-react";
import { useState } from "react";
import { useFlow, type ResultNodeData } from "@/store/flowStore";

export function ResultNode({
  id,
  data,
  selected,
}: NodeProps & { data: ResultNodeData }) {
  const removeNode = useFlow((s) => s.removeNode);
  const getLuaNode = useFlow((s) => s.getLuaNode);
  const setNodeCode = useFlow((s) => s.setNodeCode);
  const selectNode = useFlow((s) => s.selectNode);
  const [copied, setCopied] = useState(false);

  const sendToRunner = () => {
    if (!data.code) return;
    const lua = getLuaNode();
    if (!lua) return;
    setNodeCode(lua.id, data.code);
    selectNode(lua.id);
  };

  const copy = async () => {
    if (!data.code) return;
    try {
      await navigator.clipboard.writeText(data.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard denied — silently ignore */
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.18 }}
      className={`w-[320px] rounded-2xl border bg-white shadow-sm transition-shadow ${
        selected
          ? "border-mts-red shadow-[0_0_0_3px_rgba(255,0,50,0.12)]"
          : "border-mts-border"
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-mts-red !border-white"
      />

      <div className="flex items-center justify-between px-3 py-2 border-b border-mts-border">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-mts-ink text-white">
            <FileCode2 className="h-3.5 w-3.5" />
          </div>
          <div className="text-xs font-semibold text-mts-ink">
            {data.label}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] uppercase tracking-wider text-mts-muted">
            lua output
          </span>
          <button
            onClick={() => removeNode(id)}
            className="p-0.5 text-mts-muted hover:text-mts-red"
            title="Удалить ноду"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      </div>

      <pre className="text-[11px] leading-[1.45] text-mts-ink font-mono px-3 py-2 bg-mts-surface/60 overflow-auto scrollbar-thin max-h-[220px] whitespace-pre-wrap break-words nodrag nopan">
        {data.code ? data.code : "-- нажми Generate на LuaNode --"}
      </pre>

      {data.errorSummary && (
        <div className="px-3 pb-2 text-[10px] text-red-700">
          {data.errorSummary}
        </div>
      )}

      <div className="p-2 flex items-center gap-2">
        <button
          onClick={sendToRunner}
          disabled={!data.code}
          className="flex-1 inline-flex items-center justify-center gap-1.5 h-8 rounded-lg border border-mts-border text-[11px] font-medium text-mts-ink hover:bg-mts-surface disabled:opacity-50"
          title="Положить код в LuaNode-раннер"
        >
          <ArrowRightCircle className="h-3.5 w-3.5" />
          Send to Runner
        </button>
        <button
          onClick={copy}
          disabled={!data.code}
          className="inline-flex items-center justify-center gap-1.5 h-8 w-9 rounded-lg border border-mts-border text-mts-ink hover:bg-mts-surface disabled:opacity-50"
          title="Скопировать код"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-emerald-600" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
      </div>
    </motion.div>
  );
}
