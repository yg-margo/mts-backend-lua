import Editor, { type OnMount } from "@monaco-editor/react";
import { useFlow, parseInput } from "@/store/flowStore";
import { Button } from "@/components/ui/button";
import { FileCode2, Play, Loader2 } from "lucide-react";
import { runLua } from "@/lib/lua";
import { useRef } from "react";

export function EditorPanel() {
  const selectedNodeId = useFlow((s) => s.selectedNodeId);
  const nodes = useFlow((s) => s.nodes);
  const setNodeCode = useFlow((s) => s.setNodeCode);
  const setNodeRunning = useFlow((s) => s.setNodeRunning);
  const writeOutput = useFlow((s) => s.writeOutput);
  const getOutputNode = useFlow((s) => s.getOutputNode);
  const getInputNode = useFlow((s) => s.getInputNode);

  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);

  const luaNode = nodes.find(
    (n): n is Extract<typeof n, { type: "lua" }> =>
      n.id === selectedNodeId && n.type === "lua"
  );
  const code = luaNode?.data.code ?? "";
  const isRunning = !!luaNode?.data.isRunning;

  const onChange = (v: string | undefined) => {
    if (!luaNode) return;
    setNodeCode(luaNode.id, v ?? "");
  };

  const handleRun = async () => {
    if (!luaNode) return;
    const out = getOutputNode();
    const inp = getInputNode();
    const input = inp ? parseInput(inp.data.value) : undefined;
    setNodeRunning(luaNode.id, true);
    if (out) writeOutput(out.id, { stdout: [], error: undefined });
    const result = await runLua(code, { input });
    if (out) {
      writeOutput(out.id, {
        stdout: result.stdout,
        error: result.error,
        durationMs: result.durationMs,
      });
    }
    setNodeRunning(luaNode.id, false);
  };

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monaco.editor.defineTheme("mts-light", {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "8A95A5", fontStyle: "italic" },
        { token: "keyword", foreground: "D7002A", fontStyle: "bold" },
        { token: "string", foreground: "0E7C86" },
        { token: "number", foreground: "A5530F" },
        { token: "identifier", foreground: "1D2023" },
      ],
      colors: {
        "editor.background": "#FFFFFF",
        "editor.lineHighlightBackground": "#F7F7FA",
        "editorLineNumber.foreground": "#C6CBD3",
        "editorLineNumber.activeForeground": "#1D2023",
        "editorCursor.foreground": "#FF0032",
        "editor.selectionBackground": "#FFD1DC",
        "editorIndentGuide.background1": "#EDEFF3",
      },
    });
    monaco.editor.setTheme("mts-light");
  };

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center justify-between border-b border-mts-border px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-mts-ink text-white">
            <FileCode2 className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold text-mts-ink">
              Editor · {luaNode?.data.label ?? "—"}
            </div>
            <div className="text-[11px] text-mts-muted">
              {luaNode ? `id: ${luaNode.id}` : "выбери Lua-ноду в канве"}
            </div>
          </div>
        </div>
        <Button
          onClick={handleRun}
          disabled={!luaNode || isRunning}
          size="sm"
          className="rounded-lg"
        >
          {isRunning ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Run
        </Button>
      </div>

      <div className="relative flex-1">
        {luaNode ? (
          <Editor
            value={code}
            language="lua"
            onMount={handleMount}
            onChange={onChange}
            options={{
              fontSize: 13,
              fontFamily:
                '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
              minimap: { enabled: false },
              lineNumbersMinChars: 3,
              padding: { top: 14, bottom: 14 },
              renderLineHighlight: "all",
              scrollBeyondLastLine: false,
              smoothScrolling: true,
              cursorBlinking: "smooth",
              wordWrap: "on",
              tabSize: 2,
              bracketPairColorization: { enabled: true },
              scrollbar: {
                verticalScrollbarSize: 8,
                horizontalScrollbarSize: 8,
              },
            }}
            loading={
              <div className="flex h-full items-center justify-center text-sm text-mts-muted">
                загружаю редактор…
              </div>
            }
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-mts-muted">
            Нет выбранной Lua-ноды
          </div>
        )}
      </div>
    </div>
  );
}
