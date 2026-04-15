import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight, Brain, Check, AlertTriangle } from "lucide-react";
import { useThinking, type ThinkingEvent } from "@/store/thinkingStore";

const STAGE_LABELS: Record<string, string> = {
  clarifier: "Уточняю задачу",
  planner: "Планирую шаги",
  coder: "Пишу код",
  validator: "Проверяю синтаксис",
  fixer: "Чиню ошибки",
};

function useElapsed(startedAt: number, endedAt: number | null): string {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (endedAt !== null) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [endedAt]);
  const end = endedAt ?? now;
  const ms = Math.max(0, end - startedAt);
  return `${(ms / 1000).toFixed(1)}s`;
}

export function ThinkingPanel() {
  const session = useThinking((s) => s.session);
  const toggleExpanded = useThinking((s) => s.toggleExpanded);

  const elapsed = useElapsed(session?.startedAt ?? 0, session?.endedAt ?? null);

  if (!session) return null;

  const headerLabel = session.isStreaming
    ? session.currentStage
      ? STAGE_LABELS[session.currentStage] ?? "Мышление модели"
      : "Мышление модели"
    : "Ход мыслей";

  return (
    <div className="ml-11 rounded-xl border border-mts-border bg-white animate-fade-in-up overflow-hidden">
      <button
        type="button"
        onClick={toggleExpanded}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-mts-surface transition-colors"
        aria-expanded={session.expanded}
      >
        <motion.span
          animate={{ rotate: session.expanded ? 90 : 0 }}
          transition={{ duration: 0.15 }}
          className="flex h-4 w-4 items-center justify-center text-mts-muted"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </motion.span>
        <Brain className="h-3.5 w-3.5 text-mts-red" />
        <span className="text-xs font-medium text-mts-ink">{headerLabel}</span>
        {session.isStreaming && (
          <span className="h-1.5 w-1.5 rounded-full bg-mts-red animate-pulse" />
        )}
        <span className="ml-auto text-[11px] tabular-nums text-mts-muted">
          {elapsed}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {session.expanded && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden border-t border-mts-border"
          >
            <div className="flex flex-col gap-2 p-3">
              <EventList
                events={session.events}
                currentStage={session.currentStage}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function EventList({
  events,
  currentStage,
}: {
  events: ThinkingEvent[];
  currentStage: string | null;
}) {
  if (events.length === 0) {
    return (
      <div className="text-[11px] text-mts-muted italic">
        жду первый сигнал от модели…
      </div>
    );
  }

  // Group events by stage run — each "stage" event starts a new group.
  const groups: { stage: string; cycle?: number; errorMsg?: string; events: ThinkingEvent[] }[] =
    [];
  for (const ev of events) {
    if (ev.kind === "stage") {
      groups.push({
        stage: ev.stage,
        cycle: ev.cycle,
        errorMsg: ev.errorMsg,
        events: [],
      });
      continue;
    }
    if (groups.length === 0) {
      groups.push({ stage: "unknown", events: [] });
    }
    groups[groups.length - 1].events.push(ev);
  }

  return (
    <div className="flex flex-col gap-3">
      {groups.map((g, i) => (
        <StageBlock
          key={`${g.stage}-${g.cycle ?? 0}-${i}`}
          stage={g.stage}
          cycle={g.cycle}
          errorMsg={g.errorMsg}
          events={g.events}
          isActive={i === groups.length - 1 && currentStage === g.stage}
        />
      ))}
    </div>
  );
}

function StageBlock({
  stage,
  cycle,
  errorMsg,
  events,
  isActive,
}: {
  stage: string;
  cycle?: number;
  errorMsg?: string;
  events: ThinkingEvent[];
  isActive: boolean;
}) {
  const label = STAGE_LABELS[stage] ?? stage;
  const cycleLabel =
    stage === "fixer" && cycle != null ? ` · попытка №${cycle}` : "";

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            isActive ? "bg-mts-red animate-pulse" : "bg-mts-muted/50"
          }`}
        />
        <span className="text-[11px] font-medium uppercase tracking-wide text-mts-muted">
          {label}
          {cycleLabel}
        </span>
      </div>
      {errorMsg && (
        <div className="ml-3 text-[11px] text-mts-muted">
          ошибка: <span className="font-mono text-mts-ink">{errorMsg}</span>
        </div>
      )}
      {events.map((ev, idx) => (
        <StageDetail
          key={idx}
          event={ev}
          isActiveStream={isActive && ev.kind === "code_delta"}
        />
      ))}
    </div>
  );
}

function StageDetail({
  event,
  isActiveStream,
}: {
  event: ThinkingEvent;
  isActiveStream: boolean;
}) {
  if (event.kind === "plan") {
    return (
      <ol className="ml-3 list-decimal space-y-0.5 text-xs text-mts-ink">
        {event.steps.map((s, i) => (
          <li key={i} className="pl-1">
            {s}
          </li>
        ))}
      </ol>
    );
  }

  if (event.kind === "code_delta") {
    return (
      <pre className="ml-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-mts-surface px-2 py-1.5 font-mono text-[11px] text-mts-ink">
        {event.text}
        {isActiveStream && (
          <span className="inline-block w-1.5 bg-mts-red animate-pulse">
            &nbsp;
          </span>
        )}
      </pre>
    );
  }

  if (event.kind === "validator") {
    if (event.success) {
      return (
        <div className="ml-3 flex items-center gap-1.5 text-xs text-emerald-600">
          <Check className="h-3.5 w-3.5" />
          код прошёл проверку
        </div>
      );
    }
    return (
      <ul className="ml-3 space-y-0.5">
        {event.errors.map((e, i) => (
          <li
            key={i}
            className="flex items-start gap-1.5 text-[11px] text-mts-red"
          >
            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
            <span>
              {e.line != null && (
                <span className="mr-1 font-mono text-mts-muted">
                  строка {e.line}:
                </span>
              )}
              <span className="font-mono text-mts-ink">{e.message}</span>
            </span>
          </li>
        ))}
      </ul>
    );
  }

  return null;
}
