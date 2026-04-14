import { create } from "zustand";
import {
  addEdge,
  type Connection,
  type Edge,
  type Node,
  type XYPosition,
} from "@xyflow/react";

// ---------------------------------------------------------------------------
// Existing runner nodes (kept for backwards compat with EditorPanel +
// ChatPanel wiring — do not remove).
// ---------------------------------------------------------------------------

export type InputNodeData = {
  label: string;
  value: string;
};

export type LuaEntry = {
  name: string;
  params: string[];
};

export type LuaNodeData = {
  label: string;
  code: string;
  isRunning?: boolean;
  entry?: LuaEntry;
};

export type OutputNodeData = {
  label: string;
  stdout: string[];
  error?: string;
  durationMs?: number;
  lastRunAt?: number;
};

// ---------------------------------------------------------------------------
// LLM-context constructor nodes
// ---------------------------------------------------------------------------

export type PromptNodeData = {
  label: string;
  text: string;
};

export type ExampleNodeData = {
  label: string;
  code: string;
};

export type HintNodeData = {
  label: string;
  text: string;
};

export type CoderStatus = "idle" | "running" | "ok" | "error";

export type CoderNodeData = {
  label: string;
  status: CoderStatus;
  error?: string;
  usedTokens?: number;
  keptChunks?: number;
  totalChunks?: number;
  budgetTokens: number;
  lastRunAt?: number;
};

export type ResultNodeData = {
  label: string;
  code: string;
  errorSummary?: string;
};

export type AppNode =
  | (Node<InputNodeData> & { type: "input" })
  | (Node<LuaNodeData> & { type: "lua" })
  | (Node<OutputNodeData> & { type: "output" })
  | (Node<PromptNodeData> & { type: "prompt" })
  | (Node<ExampleNodeData> & { type: "example" })
  | (Node<HintNodeData> & { type: "hint" })
  | (Node<CoderNodeData> & { type: "coder" })
  | (Node<ResultNodeData> & { type: "result" });

export type AddableNodeKind =
  | "prompt"
  | "example"
  | "hint"
  | "coder"
  | "result";

const STARTER_INPUT = `{
  "name": "MTS",
  "items": [1, 2, 3, 4]
}`;

const STARTER_CODE = `-- 'input' contains the parsed JSON from the Input node.
-- Use print(...) — everything goes into the Output node.

print("hello", input.name)
local sum = 0
for _, v in ipairs(input.items) do
  sum = sum + v
end
print("sum of items:", sum)
`;

const CONTEXT_BUDGET = 2800;

const initialNodes: AppNode[] = [
  {
    id: "in-1",
    type: "input",
    position: { x: -180, y: 140 },
    data: { label: "Input", value: STARTER_INPUT },
  },
  {
    id: "lua-1",
    type: "lua",
    position: { x: 200, y: 140 },
    data: { label: "LuaNode", code: STARTER_CODE },
  },
  {
    id: "out-1",
    type: "output",
    position: { x: 580, y: 140 },
    data: { label: "Output", stdout: [] },
  },
];

const initialEdges: Edge[] = [
  {
    id: "e-in-lua",
    source: "in-1",
    target: "lua-1",
    animated: true,
  },
  {
    id: "e-lua-out",
    source: "lua-1",
    target: "out-1",
    animated: true,
  },
];

// ---------------------------------------------------------------------------
// Stable per-kind ID counter for dynamically added nodes.
// ---------------------------------------------------------------------------

const counters: Record<string, number> = {
  prompt: 0,
  example: 0,
  hint: 0,
  coder: 0,
  result: 0,
};

function nextId(kind: AddableNodeKind): string {
  counters[kind] += 1;
  return `${kind}-${counters[kind]}`;
}

function defaultDataFor(kind: AddableNodeKind): AppNode["data"] {
  switch (kind) {
    case "prompt":
      return {
        label: "Prompt",
        text: "",
      } satisfies PromptNodeData;
    case "example":
      return {
        label: "Example",
        code: "",
      } satisfies ExampleNodeData;
    case "hint":
      return {
        label: "Hint",
        text: "",
      } satisfies HintNodeData;
    case "coder":
      return {
        label: "LuaNode",
        status: "idle",
        budgetTokens: CONTEXT_BUDGET,
      } satisfies CoderNodeData;
    case "result":
      return {
        label: "Result",
        code: "",
      } satisfies ResultNodeData;
  }
}

function spawnPosition(existing: AppNode[]): XYPosition {
  // Cascade new nodes from the top-left, offset per existing count, so multiple
  // consecutive "+ Add" clicks don't stack perfectly on top of each other.
  const base = { x: -260, y: -120 };
  const step = { x: 24, y: 24 };
  const n = existing.length;
  return { x: base.x + n * step.x, y: base.y + n * step.y };
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

interface FlowState {
  nodes: AppNode[];
  edges: Edge[];
  selectedNodeId: string | null;

  setNodes: (nodes: AppNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  selectNode: (id: string | null) => void;

  addNode: (kind: AddableNodeKind, position?: XYPosition) => AppNode;
  removeNode: (id: string) => void;
  onConnect: (connection: Connection) => void;

  setNodeCode: (id: string, code: string) => void;
  setNodeEntry: (id: string, entry: LuaEntry | undefined) => void;
  setNodeRunning: (id: string, running: boolean) => void;
  setInputValue: (id: string, value: string) => void;
  writeOutput: (outputId: string, payload: Partial<OutputNodeData>) => void;

  setPromptText: (id: string, text: string) => void;
  setExampleCode: (id: string, code: string) => void;
  setHintText: (id: string, text: string) => void;
  setCoderStatus: (id: string, patch: Partial<CoderNodeData>) => void;
  setResultCode: (id: string, code: string, errorSummary?: string) => void;
  setResultFromCoder: (coderId: string, code: string) => void;

  getLuaNode: () => (AppNode & { type: "lua" }) | undefined;
  getOutputNode: () => (AppNode & { type: "output" }) | undefined;
  getInputNode: () => (AppNode & { type: "input" }) | undefined;
  getNode: (id: string) => AppNode | undefined;
}

export const useFlow = create<FlowState>((set, get) => ({
  nodes: initialNodes,
  edges: initialEdges,
  selectedNodeId: "lua-1",

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
  selectNode: (id) => set({ selectedNodeId: id }),

  addNode: (kind, position) => {
    const current = get().nodes;
    const node = {
      id: nextId(kind),
      type: kind,
      position: position ?? spawnPosition(current),
      data: defaultDataFor(kind),
    } as AppNode;
    set({ nodes: [...current, node], selectedNodeId: node.id });
    return node;
  },

  removeNode: (id) =>
    set((s) => ({
      nodes: s.nodes.filter((n) => n.id !== id),
      edges: s.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
    })),

  onConnect: (connection) =>
    set((s) => ({
      edges: addEdge(
        {
          ...connection,
          animated: true,
        },
        s.edges
      ),
    })),

  setNodeCode: (id, code) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "lua"
          ? { ...n, data: { ...n.data, code } }
          : n
      ) as AppNode[],
    })),

  setNodeEntry: (id, entry) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "lua"
          ? { ...n, data: { ...n.data, entry } }
          : n
      ) as AppNode[],
    })),

  setNodeRunning: (id, running) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "lua"
          ? { ...n, data: { ...n.data, isRunning: running } }
          : n
      ) as AppNode[],
    })),

  setInputValue: (id, value) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "input"
          ? { ...n, data: { ...n.data, value } }
          : n
      ) as AppNode[],
    })),

  writeOutput: (outputId, payload) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === outputId && n.type === "output"
          ? {
              ...n,
              data: { ...n.data, ...payload, lastRunAt: Date.now() },
            }
          : n
      ) as AppNode[],
    })),

  setPromptText: (id, text) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "prompt"
          ? { ...n, data: { ...n.data, text } }
          : n
      ) as AppNode[],
    })),

  setExampleCode: (id, code) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "example"
          ? { ...n, data: { ...n.data, code } }
          : n
      ) as AppNode[],
    })),

  setHintText: (id, text) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "hint"
          ? { ...n, data: { ...n.data, text } }
          : n
      ) as AppNode[],
    })),

  setCoderStatus: (id, patch) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "coder"
          ? {
              ...n,
              data: { ...n.data, ...patch, lastRunAt: Date.now() },
            }
          : n
      ) as AppNode[],
    })),

  setResultCode: (id, code, errorSummary) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "result"
          ? { ...n, data: { ...n.data, code, errorSummary } }
          : n
      ) as AppNode[],
    })),

  setResultFromCoder: (coderId, code) => {
    const { nodes, edges, addNode } = get();
    const downstreamResults = edges
      .filter((e) => e.source === coderId)
      .map((e) => nodes.find((n) => n.id === e.target))
      .filter((n): n is AppNode & { type: "result" } => !!n && n.type === "result");

    if (downstreamResults.length > 0) {
      set((s) => ({
        nodes: s.nodes.map((n) =>
          downstreamResults.some((r) => r.id === n.id) && n.type === "result"
            ? { ...n, data: { ...n.data, code, errorSummary: undefined } }
            : n
        ) as AppNode[],
      }));
      return;
    }

    // No result node downstream — spawn one near the coder, auto-wire the edge.
    const coder = nodes.find((n) => n.id === coderId);
    if (!coder) return;
    const spawned = addNode("result", {
      x: coder.position.x + 360,
      y: coder.position.y,
    });
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === spawned.id && n.type === "result"
          ? { ...n, data: { ...n.data, code, errorSummary: undefined } }
          : n
      ) as AppNode[],
      edges: addEdge(
        {
          source: coderId,
          target: spawned.id,
          sourceHandle: null,
          targetHandle: null,
          animated: true,
        },
        s.edges
      ),
    }));
  },

  getLuaNode: () =>
    get().nodes.find((n): n is AppNode & { type: "lua" } => n.type === "lua"),
  getOutputNode: () =>
    get().nodes.find(
      (n): n is AppNode & { type: "output" } => n.type === "output"
    ),
  getInputNode: () =>
    get().nodes.find(
      (n): n is AppNode & { type: "input" } => n.type === "input"
    ),
  getNode: (id) => get().nodes.find((n) => n.id === id),
}));

export function parseInput(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return raw;
  }
}

// ---------------------------------------------------------------------------
// Graph-walk helpers
// ---------------------------------------------------------------------------

export interface GatheredContext {
  prompts: string[];
  examples: string[];
  hints: string[];
}

/**
 * BFS upstream from `coderId`, collecting the textual payload of every
 * Prompt/Example/Hint node whose output transitively feeds into it. Traversal
 * order is deterministic (edge array order), so repeat runs produce stable
 * block ordering.
 */
export function gatherContextForCoder(
  coderId: string,
  nodes: AppNode[],
  edges: Edge[]
): GatheredContext {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const incoming = new Map<string, string[]>();
  for (const e of edges) {
    if (!incoming.has(e.target)) incoming.set(e.target, []);
    incoming.get(e.target)!.push(e.source);
  }

  const visited = new Set<string>();
  const stack = [coderId];
  const orderedSources: string[] = [];

  while (stack.length) {
    const id = stack.pop()!;
    const parents = incoming.get(id) ?? [];
    for (const p of parents) {
      if (visited.has(p)) continue;
      visited.add(p);
      orderedSources.push(p);
      stack.push(p);
    }
  }

  const prompts: string[] = [];
  const examples: string[] = [];
  const hints: string[] = [];

  for (const id of orderedSources) {
    const n = byId.get(id);
    if (!n) continue;
    if (n.type === "prompt" && n.data.text.trim()) {
      prompts.push(n.data.text.trim());
    } else if (n.type === "example" && n.data.code.trim()) {
      examples.push(n.data.code.trim());
    } else if (n.type === "hint" && n.data.text.trim()) {
      hints.push(n.data.text.trim());
    }
  }

  return { prompts, examples, hints };
}
