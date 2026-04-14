import { create } from "zustand";

export type ChatRole = "user" | "assistant" | "error";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  code?: string;
  partialCode?: string;
  hint?: string;
  createdAt: number;
}

interface ChatState {
  messages: ChatMessage[];
  isGenerating: boolean;
  append: (m: Omit<ChatMessage, "id" | "createdAt">) => ChatMessage;
  setGenerating: (v: boolean) => void;
  clear: () => void;
}

export const useChat = create<ChatState>((set) => ({
  messages: [],
  isGenerating: false,
  append: (m) => {
    const full: ChatMessage = {
      ...m,
      id: crypto.randomUUID(),
      createdAt: Date.now(),
    };
    set((s) => ({ messages: [...s.messages, full] }));
    return full;
  },
  setGenerating: (v) => set({ isGenerating: v }),
  clear: () => set({ messages: [] }),
}));
