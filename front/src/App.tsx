import {
  PanelGroup,
  Panel,
  PanelResizeHandle,
} from "react-resizable-panels";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { EditorPanel } from "@/components/editor/EditorPanel";
import { FlowPanel } from "@/components/flow/FlowPanel";

function Handle() {
  return (
    <PanelResizeHandle className="w-px bg-mts-border hover:bg-mts-red/40 transition-colors data-[resize-handle-active]:bg-mts-red" />
  );
}

function Header() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-mts-border bg-white px-5">
      <div className="flex items-center gap-3">
        <MtsMark />
        <div className="flex items-baseline gap-2">
          <span className="text-base font-bold tracking-tight text-mts-ink">
            LocalScript
          </span>
          <span className="text-xs text-mts-muted">· Lua Studio</span>
        </div>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-mts-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          local LLM · Ollama
        </span>
        <span className="hidden sm:inline">v0.1</span>
      </div>
    </header>
  );
}

function MtsMark() {
  return (
    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-mts-red text-white font-black text-[11px] tracking-wider shadow-sm">
      MTS
    </div>
  );
}

export default function App() {
  return (
    <div className="flex h-screen w-screen flex-col bg-white text-mts-ink">
      <Header />
      <div className="flex-1 min-h-0">
        <PanelGroup direction="horizontal" autoSaveId="mts-lua-layout">
          <Panel defaultSize={28} minSize={20}>
            <ChatPanel />
          </Panel>
          <Handle />
          <Panel defaultSize={36} minSize={22}>
            <EditorPanel />
          </Panel>
          <Handle />
          <Panel defaultSize={36} minSize={22}>
            <FlowPanel />
          </Panel>
        </PanelGroup>
      </div>
    </div>
  );
}
