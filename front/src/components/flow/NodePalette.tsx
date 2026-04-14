import {
  MessageCircle,
  BookOpen,
  Lightbulb,
  Sparkles,
  FileCode2,
  Plus,
} from "lucide-react";
import { useFlow, type AddableNodeKind } from "@/store/flowStore";

interface PaletteItem {
  kind: AddableNodeKind;
  label: string;
  icon: typeof MessageCircle;
  tint: string;
}

const ITEMS: PaletteItem[] = [
  { kind: "prompt", label: "Prompt", icon: MessageCircle, tint: "bg-mts-red" },
  { kind: "example", label: "Example", icon: BookOpen, tint: "bg-mts-ink" },
  { kind: "hint", label: "Hint", icon: Lightbulb, tint: "bg-amber-400" },
  { kind: "coder", label: "LuaNode", icon: Sparkles, tint: "bg-mts-red" },
  { kind: "result", label: "Result", icon: FileCode2, tint: "bg-mts-ink" },
];

export function NodePalette() {
  const addNode = useFlow((s) => s.addNode);

  return (
    <div className="pointer-events-auto absolute left-3 top-3 z-10 flex items-center gap-1.5 rounded-xl border border-mts-border bg-white/95 px-2 py-1.5 shadow-sm backdrop-blur">
      <div className="flex h-6 items-center gap-1 pr-1.5 text-[10px] font-semibold uppercase tracking-wider text-mts-muted">
        <Plus className="h-3 w-3" />
        add node
      </div>
      {ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <button
            key={item.kind}
            onClick={() => addNode(item.kind)}
            className="inline-flex h-7 items-center gap-1.5 rounded-lg border border-mts-border bg-white px-2 text-[11px] font-medium text-mts-ink hover:bg-mts-surface"
            title={`Добавить ${item.label}-ноду`}
          >
            <span
              className={`flex h-4 w-4 items-center justify-center rounded ${item.tint} text-white`}
            >
              <Icon className="h-2.5 w-2.5" />
            </span>
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
