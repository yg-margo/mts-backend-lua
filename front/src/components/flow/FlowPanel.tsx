import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  BackgroundVariant,
  applyNodeChanges,
  applyEdgeChanges,
  type NodeChange,
  type EdgeChange,
  type Connection,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Workflow } from "lucide-react";
import { useFlow, type AppNode } from "@/store/flowStore";
import { InputNode } from "./nodes/InputNode";
import { LuaNode } from "./nodes/LuaNode";
import { OutputNode } from "./nodes/OutputNode";
import { PromptNode } from "./nodes/PromptNode";
import { ExampleNode } from "./nodes/ExampleNode";
import { HintNode } from "./nodes/HintNode";
import { CoderNode } from "./nodes/CoderNode";
import { ResultNode } from "./nodes/ResultNode";
import { NodePalette } from "./NodePalette";

const nodeTypes = {
  input: InputNode,
  lua: LuaNode,
  output: OutputNode,
  prompt: PromptNode,
  example: ExampleNode,
  hint: HintNode,
  coder: CoderNode,
  result: ResultNode,
} as const;

export function FlowPanel() {
  const nodes = useFlow((s) => s.nodes);
  const edges = useFlow((s) => s.edges);
  const setNodes = useFlow((s) => s.setNodes);
  const setEdges = useFlow((s) => s.setEdges);
  const selectNode = useFlow((s) => s.selectNode);
  const onConnect = useFlow((s) => s.onConnect);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes(applyNodeChanges(changes, nodes as Node[]) as AppNode[]);
    },
    [nodes, setNodes]
  );
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges(applyEdgeChanges(changes, edges));
    },
    [edges, setEdges]
  );

  const handleConnect = useCallback(
    (c: Connection) => onConnect(c),
    [onConnect]
  );

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      selectNode(node.id);
    },
    [selectNode]
  );

  const types = useMemo(() => nodeTypes, []);

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center gap-2 border-b border-mts-border px-4 py-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-mts-ink text-white">
          <Workflow className="h-4 w-4" />
        </div>
        <div>
          <div className="text-sm font-semibold text-mts-ink">Flow</div>
          <div className="text-[11px] text-mts-muted">
            конструктор контекста LLM · tree-sitter packing
          </div>
        </div>
      </div>

      <div className="relative flex-1">
        <NodePalette />
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={handleConnect}
          onNodeClick={onNodeClick}
          nodeTypes={types}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{
            animated: true,
            style: { stroke: "#CBD5E1", strokeWidth: 1.5 },
          }}
          deleteKeyCode={["Backspace", "Delete"]}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={18}
            size={1.2}
            color="#E4E7EC"
          />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}
