import { create } from "zustand";
import type { WsStage, WsValidatorError } from "@/lib/ws";

export type ThinkingStage = WsStage;

export type ThinkingEvent =
  | { kind: "stage"; stage: ThinkingStage; cycle?: number; errorMsg?: string }
  | { kind: "plan"; steps: string[] }
  | { kind: "snippet"; preview: string }
  | {
      kind: "code_delta";
      stage: "coder" | "fixer";
      text: string;
      cycle?: number;
    }
  | { kind: "validator"; success: boolean; errors: WsValidatorError[] };

export interface ThinkingSession {
  events: ThinkingEvent[];
  currentStage: ThinkingStage | null;
  currentCycle: number | null;
  isStreaming: boolean;
  expanded: boolean;
  startedAt: number;
  endedAt: number | null;
}

interface ThinkingState {
  session: ThinkingSession | null;
  start: () => void;
  appendEvent: (event: ThinkingEvent) => void;
  appendToken: (
    stage: "coder" | "fixer",
    text: string,
    cycle?: number
  ) => void;
  setStage: (stage: ThinkingStage, cycle?: number, errorMsg?: string) => void;
  finish: () => void;
  reset: () => void;
  toggleExpanded: () => void;
}

const emptySession = (): ThinkingSession => ({
  events: [],
  currentStage: null,
  currentCycle: null,
  isStreaming: true,
  expanded: false,
  startedAt: Date.now(),
  endedAt: null,
});

export const useThinking = create<ThinkingState>((set) => ({
  session: null,

  start: () => set({ session: emptySession() }),

  reset: () => set({ session: null }),

  toggleExpanded: () =>
    set((s) => {
      if (!s.session) return s;
      return { session: { ...s.session, expanded: !s.session.expanded } };
    }),

  setStage: (stage, cycle, errorMsg) =>
    set((s) => {
      if (!s.session) return s;
      return {
        session: {
          ...s.session,
          currentStage: stage,
          currentCycle: cycle ?? null,
          events: [
            ...s.session.events,
            { kind: "stage", stage, cycle, errorMsg },
          ],
        },
      };
    }),

  appendEvent: (event) =>
    set((s) => {
      if (!s.session) return s;
      return {
        session: {
          ...s.session,
          events: [...s.session.events, event],
        },
      };
    }),

  appendToken: (stage, text, cycle) =>
    set((s) => {
      if (!s.session) return s;
      const events = s.session.events;
      const lastIdx = events.length - 1;
      const last = events[lastIdx];
      // Coalesce consecutive tokens of the same (stage, cycle) into one code_delta.
      if (
        last &&
        last.kind === "code_delta" &&
        last.stage === stage &&
        last.cycle === cycle
      ) {
        const next = [...events];
        next[lastIdx] = { ...last, text: last.text + text };
        return { session: { ...s.session, events: next } };
      }
      return {
        session: {
          ...s.session,
          events: [...events, { kind: "code_delta", stage, text, cycle }],
        },
      };
    }),

  finish: () =>
    set((s) => {
      if (!s.session) return s;
      return {
        session: {
          ...s.session,
          isStreaming: false,
          endedAt: Date.now(),
          currentStage: null,
        },
      };
    }),
}));
