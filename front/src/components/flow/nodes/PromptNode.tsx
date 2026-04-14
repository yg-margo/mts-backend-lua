import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { MessageCircle, X } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { useFlow, type PromptNodeData } from "@/store/flowStore";

export function PromptNode({
  id,
  data,
  selected,
}: NodeProps & { data: PromptNodeData }) {
  const setPromptText = useFlow((s) => s.setPromptText);
  const removeNode = useFlow((s) => s.removeNode);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.18 }}
      className={`w-[280px] rounded-2xl border bg-white shadow-sm transition-shadow ${
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
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-mts-red text-white">
            <MessageCircle className="h-3.5 w-3.5" />
          </div>
          <div className="text-xs font-semibold text-mts-ink">
            {data.label}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] uppercase tracking-wider text-mts-muted">
            prompt
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
          value={data.text}
          onChange={(e) => setPromptText(id, e.target.value)}
          className="text-[12px] leading-[1.45] min-h-[80px] max-h-[160px] resize-y scrollbar-thin border-mts-border/70 bg-mts-surface/60 p-2 nodrag nopan"
          onMouseDownCapture={(e) => e.stopPropagation()}
          spellCheck={false}
          placeholder="напр. Посчитай сумму элементов input.items"
        />
        <div className="mt-1.5 text-[10px] text-mts-muted">
          натуральный язык → в Task
        </div>
      </div>
    </motion.div>
  );
}
