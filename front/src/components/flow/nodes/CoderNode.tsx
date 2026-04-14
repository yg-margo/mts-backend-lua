import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { Sparkles, Loader2, X, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  gatherContextForCoder,
  useFlow,
  type CoderNodeData,
} from "@/store/flowStore";
import { generateFromContext, type ContextBlock } from "@/lib/api";

export function CoderNode({
  id,
  data,
  selected,
}: NodeProps & { data: CoderNodeData }) {
  const setCoderStatus = useFlow((s) => s.setCoderStatus);
  const removeNode = useFlow((s) => s.removeNode);
  const setResultFromCoder = useFlow((s) => s.setResultFromCoder);

  const onGenerate = async () => {
    const { nodes, edges } = useFlow.getState();
    const ctx = gatherContextForCoder(id, nodes, edges);

    if (ctx.prompts.length === 0) {
      setCoderStatus(id, {
        status: "error",
        error: "Нужна как минимум одна Prompt-нода, подключённая к LuaNode.",
      });
      return;
    }

    const [head, ...extraPrompts] = ctx.prompts;
    const blocks: ContextBlock[] = [
      ...extraPrompts.map((p) => ({ kind: "prompt" as const, content: p })),
      ...ctx.examples.map((c) => ({ kind: "example" as const, content: c })),
      ...ctx.hints.map((h) => ({ kind: "hint" as const, content: h })),
    ];

    setCoderStatus(id, {
      status: "running",
      error: undefined,
      usedTokens: undefined,
      keptChunks: undefined,
      totalChunks: undefined,
    });

    try {
      const result = await generateFromContext({ prompt: head, blocks });
      if (result.ok) {
        setCoderStatus(id, {
          status: "ok",
          error: undefined,
          usedTokens: result.usedTokens,
          keptChunks: result.keptChunks,
          totalChunks: result.totalChunks,
        });
        setResultFromCoder(id, result.code);
      } else {
        setCoderStatus(id, {
          status: "error",
          error: result.message,
        });
        if (result.partialCode) {
          setResultFromCoder(id, result.partialCode);
        }
      }
    } catch (e) {
      setCoderStatus(id, {
        status: "error",
        error: e instanceof Error ? e.message : "Сетевая ошибка",
      });
    }
  };

  const pct =
    data.usedTokens !== undefined && data.budgetTokens > 0
      ? Math.min(100, Math.round((data.usedTokens / data.budgetTokens) * 100))
      : 0;

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
            <Sparkles className="h-3.5 w-3.5" />
          </div>
          <div className="text-xs font-semibold text-mts-ink">
            {data.label}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] uppercase tracking-wider text-mts-muted">
            LLM lua node
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

      <div className="p-3 space-y-2">
        <Button
          onClick={onGenerate}
          disabled={data.status === "running"}
          size="sm"
          className="w-full h-8 rounded-lg"
        >
          {data.status === "running" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
          {data.status === "running" ? "Генерирую…" : "Generate"}
        </Button>

        {/* Token budget meter */}
        <div>
          <div className="flex items-center justify-between text-[10px] text-mts-muted">
            <span>context budget (tree-sitter)</span>
            <span>
              {data.usedTokens ?? 0} / {data.budgetTokens} tok
            </span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-mts-border/60">
            <div
              className={`h-full transition-all ${
                pct < 75
                  ? "bg-emerald-500"
                  : pct < 95
                    ? "bg-amber-500"
                    : "bg-mts-red"
              }`}
              style={{ width: `${pct}%` }}
            />
          </div>
          {data.totalChunks !== undefined && (
            <div className="mt-1 text-[10px] text-mts-muted">
              chunks: {data.keptChunks}/{data.totalChunks} kept
            </div>
          )}
        </div>

        {/* Status badge */}
        {data.status === "ok" && (
          <div className="flex items-center gap-1.5 rounded-md bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">
            <CheckCircle2 className="h-3 w-3" />
            <span>готово — код в Result-ноде</span>
          </div>
        )}
        {data.status === "error" && data.error && (
          <div className="flex items-start gap-1.5 rounded-md bg-red-50 px-2 py-1 text-[11px] text-red-700">
            <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
            <span className="whitespace-pre-wrap break-words">
              {data.error}
            </span>
          </div>
        )}
        {data.status === "idle" && (
          <div className="text-[10px] text-mts-muted">
            подключи Prompt / Example / Hint → нажми Generate
          </div>
        )}
      </div>
    </motion.div>
  );
}
