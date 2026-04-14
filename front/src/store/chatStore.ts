import { create } from "zustand";

export type ChatRole = "user" | "assistant" | "error";

export type ClarificationStatus = "pending" | "answered" | "expired";

export interface ClarificationState {
  sessionId: string;
  questions: string[];
  answers?: string[];
  status: ClarificationStatus;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  code?: string;
  inputs?: Record<string, unknown>;
  entryPoint?: { name: string; params: string[] };
  partialCode?: string;
  hint?: string;
  clarification?: ClarificationState;
  createdAt: number;
}

export type ChatMessagePatch = Partial<Omit<ChatMessage, "id" | "createdAt">>;

interface ChatState {
  messages: ChatMessage[];
  isGenerating: boolean;
  chatSessionId: string | null;
  append: (m: Omit<ChatMessage, "id" | "createdAt">) => ChatMessage;
  update: (id: string, patch: ChatMessagePatch) => void;
  setGenerating: (v: boolean) => void;
  setChatSessionId: (id: string | null) => void;
  clear: () => void;
}

export const useChat = create<ChatState>((set) => ({
  messages: [],
  isGenerating: false,
  chatSessionId: null,
  append: (m) => {
    const full: ChatMessage = {
      ...m,
      id: crypto.randomUUID(),
      createdAt: Date.now(),
    };
    set((s) => ({ messages: [...s.messages, full] }));
    return full;
  },
  update: (id, patch) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    })),
  setGenerating: (v) => set({ isGenerating: v }),
  setChatSessionId: (id) => set({ chatSessionId: id }),
  clear: () => set({ messages: [], chatSessionId: null }),
}));

export const hasPendingClarification = (messages: ChatMessage[]): boolean =>
  messages.some((m) => m.clarification?.status === "pending");
