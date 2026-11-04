/** Analysis envelope types — mirror of the engine's JSON response. */

export interface Diagnostic {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  line: number | null;
  col: number | null;
  layer: string;
  hint: string | null;
  context_line: string | null;
  evidence: string | null;
  /** violation | risk | note | unsupported — what kind of knowledge this is */
  classification: string;
  /** machine-readable quantities (bounds, capacities, mode) */
  detail: Record<string, unknown> | null;
  /** deterministic traceable identity */
  finding_id: string;
}

export interface Coverage {
  statements_total: number;
  statements_analyzed: number;
  findings: { violation: number; risk: number; note: number };
  needs_human_review: number;
}

export interface Assumption {
  id: string;
  topic: string;
  detail: string;
}

export interface SemanticSymbol {
  name: string;
  level: number;
  section: string;
  line: number;
  col: number;
  usage: string | null;
  usage_label: string;
  elementary: boolean;
  category: string;
  picture: string | null;
  signed: boolean | null;
  integer_digits: number | null;
  fractional_digits: number | null;
  digits: number | null;
  byte_length: number | null;
  sign: string | null;
  value: string | null;
  parent: string | null;
  children: SemanticSymbol[];
}

export interface SemanticRef {
  name: string;
  resolved: string;
  role: string;
  statement: string;
  line: number | null;
  col: number | null;
}

export interface SemanticCounts {
  data_items: number;
  references: number;
  declared_identifiers: number;
}

export interface Token {
  type: string;
  text: string;
  line: number;
  col: number;
}

export interface PicExpansion {
  signed: boolean;
  int_digits: number;
  frac_digits: number;
}

export interface SymbolRow {
  name: string;
  level: number;
  section: string;
  line: number;
  col: number;
  usage: string | null;
  elementary: boolean;
  picture?: string | null;
  expanded?: PicExpansion | null;
  sign?: string | null;
  value?: string | null;
  children?: SymbolRow[];
}

export interface Span {
  line: number | null;
  col: number | null;
}

export interface AstNode {
  type: string;
  span?: Span;
  [key: string]: unknown;
}

export interface AnalysisResponse {
  meta: { name: string; bytes: number; lines: number; columns_per_line: number };
  layers: { layer: string; status: "passed" | "failed" | "skipped"; diagnostics?: number }[];
  diagnostics: Diagnostic[];
  tokens: Token[];
  ast: Record<string, unknown> | null;
  symbols: SemanticSymbol[] | null;
  references: SemanticRef[] | null;
  semantic_counts: SemanticCounts | null;
  coverage: Coverage | null;
  assumptions: Assumption[] | null;
  schema_version: number;
  summary: {
    ok: boolean;
    errors: number;
    warnings: number;
    infos: number;
    token_count: number;
    failed_layer: string | null;
    program_name: string | null;
    is_initial: boolean | null;
    using: string[] | null;
  };
}

export interface SampleMeta {
  id: string;
  filename: string;
  title: string;
  origin: string;
  description: string;
  note: string;
  expect_ok: boolean;
  source: string;
}

export interface HealthInfo {
  status: string;
  engine: string;
  version: string;
}

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
    this.name = "ApiError";
  }
}

async function readError(res: Response): Promise<never> {
  let code = `HTTP_${res.status}`;
  let message = res.statusText || "request failed";
  try {
    const body = (await res.json()) as { error?: { code?: string; message?: string } };
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    }
  } catch {
    /* keep defaults */
  }
  throw new ApiError(code, message, res.status);
}

export async function getHealth(): Promise<HealthInfo> {
  const res = await fetch("/api/health");
  if (!res.ok) await readError(res);
  return (await res.json()) as HealthInfo;
}

export async function getSamples(): Promise<SampleMeta[]> {
  const res = await fetch("/api/samples");
  if (!res.ok) await readError(res);
  const body = (await res.json()) as { samples: SampleMeta[] };
  return body.samples;
}

export async function analyzeSource(
  source: string,
  filename: string,
): Promise<AnalysisResponse> {
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, filename }),
  });
  if (!res.ok) await readError(res);
  return (await res.json()) as AnalysisResponse;
}
