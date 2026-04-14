import { create } from "zustand";
import type { Edge, Node } from "@xyflow/react";

export type InputNodeData = {
  label: string;
  value: string;
};

export type LuaNodeData = {
  label: string;
  code: string;
  isRunning?: boolean;
};

export type OutputNodeData = {
  label: string;
  stdout: string[];
  error?: string;
  durationMs?: number;
  lastRunAt?: number;
};

export type AppNode =
  | (Node<InputNodeData> & { type: "input" })
  | (Node<LuaNodeData> & { type: "lua" })
  | (Node<OutputNodeData> & { type: "output" });

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

interface FlowState {
  nodes: AppNode[];
  edges: Edge[];
  selectedNodeId: string | null;
  setNodes: (nodes: AppNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  selectNode: (id: string | null) => void;
  setNodeCode: (id: string, code: string) => void;
  setNodeRunning: (id: string, running: boolean) => void;
  setInputValue: (id: string, value: string) => void;
  writeOutput: (
    outputId: string,
    payload: Partial<OutputNodeData>
  ) => void;
  getLuaNode: () => (AppNode & { type: "lua" }) | undefined;
  getOutputNode: () => (AppNode & { type: "output" }) | undefined;
  getInputNode: () => (AppNode & { type: "input" }) | undefined;
}

export const useFlow = create<FlowState>((set, get) => ({
  nodes: initialNodes,
  edges: initialEdges,
  selectedNodeId: "lua-1",
  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
  selectNode: (id) => set({ selectedNodeId: id }),
  setNodeCode: (id, code) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id && n.type === "lua"
          ? { ...n, data: { ...n.data, code } }
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
              data: {
                ...n.data,
                ...payload,
                lastRunAt: Date.now(),
              },
            }
          : n
      ) as AppNode[],
    })),
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
