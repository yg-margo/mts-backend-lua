export interface GenerateRequest {
  prompt: string;
}

export interface GenerateFollowupRequest {
  session_id: string;
  answers: string[];
}

export interface EntryPoint {
  name: string;
  params: string[];
}

export interface GenerateCode {
  ok: "code";
  code: string;
  inputs: Record<string, unknown> | null;
  entryPoint: EntryPoint | null;
}

export interface GenerateClarify {
  ok: "clarify";
  sessionId: string;
  questions: string[];
}

export interface GenerateError {
  ok: "error";
  status: number;
  message: string;
  errors: Array<{ line: number | null; message: string }>;
  partialCode: string;
  hint: string;
}

export type GenerateResult = GenerateCode | GenerateClarify | GenerateError;

export interface ContextBlock {
  kind: "prompt" | "example" | "hint";
  content: string;
}

export interface GenerateFromContextRequest {
  prompt: string;
  blocks: ContextBlock[];
}

export interface GenerateFromContextSuccess {
  ok: true;
  code: string;
  usedTokens: number;
  keptChunks: number;
  totalChunks: number;
  inputs: Record<string, unknown>;
  entryPoint: EntryPoint | null;
}

export interface GenerateFromContextFailure {
  ok: false;
  status: number;
  message: string;
  errors: Array<{ line: number | null; message: string }>;
  partialCode: string;
  hint: string;
}

export type GenerateFromContextResult =
  | GenerateFromContextSuccess
  | GenerateFromContextFailure;

const BASE =
  (import.meta as unknown as { env: Record<string, string> }).env
    ?.VITE_API_URL ?? "";

interface ErrorDetailBody {
  message?: string;
  errors?: Array<{ line: number | null; message: string }>;
  partial_code?: string;
  hint?: string;
}

interface FailureShape {
  status: number;
  message: string;
  errors: Array<{ line: number | null; message: string }>;
  partialCode: string;
  hint: string;
}

function parseFailureShape(
  status: number,
  detail: string | ErrorDetailBody | undefined
): FailureShape {
  if (typeof detail === "string") {
    return { status, message: detail, errors: [], partialCode: "", hint: "" };
  }
  const d = detail ?? {};
  return {
    status,
    message: d.message ?? `HTTP ${status}`,
    errors: d.errors ?? [],
    partialCode: d.partial_code ?? "",
    hint: d.hint ?? "",
  };
}

interface BackendGenerateResponse {
  code?: string;
  inputs?: Record<string, unknown> | null;
  entry_point?: { name: string; params: string[] } | null;
  clarification?: { session_id: string; questions: string[] };
}

function parseGenerateResponse(data: BackendGenerateResponse): GenerateResult {
  if (data.clarification) {
    return {
      ok: "clarify",
      sessionId: data.clarification.session_id,
      questions: data.clarification.questions ?? [],
    };
  }
  return {
    ok: "code",
    code: data.code ?? "",
    inputs: data.inputs ?? null,
    entryPoint: data.entry_point
      ? { name: data.entry_point.name, params: data.entry_point.params }
      : null,
  };
}

async function postGenerate(
  body: GenerateRequest | GenerateFollowupRequest
): Promise<GenerateResult> {
  const res = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (res.ok) {
    const data = (await res.json()) as BackendGenerateResponse;
    return parseGenerateResponse(data);
  }

  const errBody = (await res.json().catch(() => ({}))) as {
    detail?: string | ErrorDetailBody;
  };
  return { ok: "error", ...parseFailureShape(res.status, errBody.detail) };
}

export function generateCode(prompt: string): Promise<GenerateResult> {
  return postGenerate({ prompt } satisfies GenerateRequest);
}

export function submitClarificationAnswers(
  sessionId: string,
  answers: string[]
): Promise<GenerateResult> {
  return postGenerate({
    session_id: sessionId,
    answers,
  } satisfies GenerateFollowupRequest);
}

export async function generateFromContext(
  payload: GenerateFromContextRequest
): Promise<GenerateFromContextResult> {
  const res = await fetch(`${BASE}/generate-from-context`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (res.ok) {
    const data = (await res.json()) as {
      code: string;
      used_tokens: number;
      kept_chunks: number;
      total_chunks: number;
      inputs?: Record<string, unknown>;
      entry_point?: { name: string; params: string[] } | null;
    };
    return {
      ok: true,
      code: data.code,
      usedTokens: data.used_tokens,
      keptChunks: data.kept_chunks,
      totalChunks: data.total_chunks,
      inputs: data.inputs ?? {},
      entryPoint: data.entry_point
        ? { name: data.entry_point.name, params: data.entry_point.params }
        : null,
    };
  }

  const body = (await res.json().catch(() => ({}))) as {
    detail?: string | ErrorDetailBody;
  };
  return { ok: false, ...parseFailureShape(res.status, body.detail) };
}
