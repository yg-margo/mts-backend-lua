import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { Play, Loader2, Code2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useFlow, parseInput, type LuaNodeData } from "@/store/flowStore";
import { runLua } from "@/lib/lua";

export function LuaNode({ id, data, selected }: NodeProps & { data: LuaNodeData }) {
  const setNodeRunning = useFlow((s) => s.setNodeRunning);
  const writeOutput = useFlow((s) => s.writeOutput);
  const getOutputNode = useFlow((s) => s.getOutputNode);
  const getInputNode = useFlow((s) => s.getInputNode);

  const onRun = async () => {
    const out = getOutputNode();
    const inp = getInputNode();
    const input = inp ? parseInput(inp.data.value) : undefined;
    setNodeRunning(id, true);
    if (out) writeOutput(out.id, { stdout: [], error: undefined });

    // If we know the generated entry-point, auto-invoke it with input.<param>
    // values. Wrap user code in an IIFE so a top-level `return` in it doesn't
    // make the trailing print(...) syntactically unreachable.
    let codeToRun = data.code;
    if (data.entry?.name) {
      const argList = data.entry.params.map((p) => `input.${p}`).join(", ");
      codeToRun = `(function()\n${data.code}\nend)()\nprint(${data.entry.name}(${argList}))`;
    }

    const result = await runLua(codeToRun, { input });
    if (out)
      writeOutput(out.id, {
        stdout: result.stdout,
        error: result.error,
        durationMs: result.durationMs,
      });
    setNodeRunning(id, false);
  };

  const preview = (data.code ?? "")
    .split("\n")
    .slice(0, 5)
    .join("\n");

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
        type="target"
        position={Position.Left}
        className="!bg-mts-red !border-white"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-mts-red !border-white"
      />
      <div className="flex items-center justify-between px-3 py-2 border-b border-mts-border">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-mts-red text-white">
            <Code2 className="h-3.5 w-3.5" />
          </div>
          <div className="text-xs font-semibold text-mts-ink">{data.label}</div>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-mts-muted">
          lua
        </span>
      </div>

      <pre className="text-[11px] leading-[1.4] text-mts-ink font-mono px-3 py-2 bg-mts-surface/60 overflow-hidden line-clamp-5 min-h-[70px]">
        {preview || "-- empty --"}
      </pre>

      <div className="p-2">
        <Button
          onClick={onRun}
          disabled={data.isRunning}
          size="sm"
          className="w-full h-8 rounded-lg"
        >
          {data.isRunning ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
          Run
        </Button>
      </div>
    </motion.div>
  );
}
