import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { BookOpen, X } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { useFlow, type ExampleNodeData } from "@/store/flowStore";

function approxTokens(text: string): number {
  // Rough client-side estimate — real count runs on the backend via tiktoken.
  // 1 token ≈ 4 chars is good enough for a meter.
  return Math.max(0, Math.ceil(text.length / 4));
}

export function ExampleNode({
  id,
  data,
  selected,
}: NodeProps & { data: ExampleNodeData }) {
  const setExampleCode = useFlow((s) => s.setExampleCode);
  const removeNode = useFlow((s) => s.removeNode);
  const tokens = approxTokens(data.code);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.18 }}
      className={`w-[300px] rounded-2xl border bg-white shadow-sm transition-shadow ${
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
            <BookOpen className="h-3.5 w-3.5" />
          </div>
          <div className="text-xs font-semibold text-mts-ink">
            {data.label}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] uppercase tracking-wider text-mts-muted">
            lua example
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

      <div className="p-2">
        <Textarea
          value={data.code}
          onChange={(e) => setExampleCode(id, e.target.value)}
          className="text-[11px] font-mono leading-[1.45] min-h-[140px] max-h-[260px] resize-y scrollbar-thin border-mts-border/70 bg-mts-surface/60 p-2 nodrag nopan"
          onMouseDownCapture={(e) => e.stopPropagation()}
          spellCheck={false}
          placeholder={`-- helper\nfunction sum(t)\n  local s = 0\n  for _, v in ipairs(t) do s = s + v end\n  return s\nend`}
        />
        <div className="mt-1.5 flex items-center justify-between text-[10px] text-mts-muted">
          <span>tree-sitter → AST-чанки</span>
          <span>~{tokens} tok</span>
        </div>
      </div>
    </motion.div>
  );
}
