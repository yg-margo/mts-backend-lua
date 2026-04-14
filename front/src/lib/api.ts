export interface GenerateRequest {
  prompt: string;
}

export interface GenerateSuccess {
  ok: true;
  code: string;
}

export interface GenerateFailure {
  ok: false;
  status: number;
  message: string;
  errors: Array<{ line: number | null; message: string }>;
  partialCode: string;
  hint: string;
}

export type GenerateResult = GenerateSuccess | GenerateFailure;

const BASE =
  (import.meta as unknown as { env: Record<string, string> }).env
    ?.VITE_API_URL ?? "";

export async function generateCode(prompt: string): Promise<GenerateResult> {
  const res = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt } satisfies GenerateRequest),
  });

  if (res.ok) {
    const data = (await res.json()) as { code: string };
    return { ok: true, code: data.code };
  }

  const body = (await res.json().catch(() => ({}))) as {
    detail?:
      | string
      | {
          message?: string;
          errors?: Array<{ line: number | null; message: string }>;
          partial_code?: string;
          hint?: string;
        };
  };

  if (typeof body.detail === "string") {
    return {
      ok: false,
      status: res.status,
      message: body.detail,
      errors: [],
      partialCode: "",
      hint: "",
    };
  }

  const d = body.detail ?? {};
  return {
    ok: false,
    status: res.status,
    message: d.message ?? `HTTP ${res.status}`,
    errors: d.errors ?? [],
    partialCode: d.partial_code ?? "",
    hint: d.hint ?? "",
  };
}
