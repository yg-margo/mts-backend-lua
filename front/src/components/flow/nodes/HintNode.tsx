import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { Lightbulb, X } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { useFlow, type HintNodeData } from "@/store/flowStore";

export function HintNode({
  id,
  data,
  selected,
}: NodeProps & { data: HintNodeData }) {
  const setHintText = useFlow((s) => s.setHintText);
  const removeNode = useFlow((s) => s.removeNode);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.18 }}
      className={`w-[260px] rounded-2xl border bg-amber-50/60 shadow-sm transition-shadow ${
        selected
          ? "border-mts-red shadow-[0_0_0_3px_rgba(255,0,50,0.12)]"
          : "border-amber-200"
      }`}
    >
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-amber-400 !border-white"
      />

      <div className="flex items-center justify-between px-3 py-2 border-b border-amber-200">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-400 text-white">
            <Lightbulb className="h-3.5 w-3.5" />
          </div>
          <div className="text-xs font-semibold text-mts-ink">
            {data.label}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] uppercase tracking-wider text-amber-700">
            hint
          </span>
          <button
            onClick={() => removeNode(id)}
            className="p-0.5 text-amber-700 hover:text-mts-red"
            title="Удалить ноду"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      </div>

      <div className="p-2">
        <Textarea
          value={data.text}
          onChange={(e) => setHintText(id, e.target.value)}
          className="text-[12px] leading-[1.4] min-h-[52px] max-h-[120px] resize-y scrollbar-thin border-amber-200/70 bg-white p-2 nodrag nopan"
          onMouseDownCapture={(e) => e.stopPropagation()}
          spellCheck={false}
          placeholder="напр. используй wf.vars.data, без внешних библиотек"
        />
        <div className="mt-1.5 text-[10px] text-amber-700/80">
          добавится буллетом в Hints
        </div>
      </div>
    </motion.div>
  );
}
