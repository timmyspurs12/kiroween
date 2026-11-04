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

// ---- project intelligence (Milestone 3) ---------------------------------

export interface ProjectFile {
  file_id: string;
  path: string;
  kind: "program" | "copybook";
  bytes: number;
  lines: number;
}

export interface ProjectEdge {
  kind: "copy" | "call";
  from: string;
  to: string | null;
  target: string;
  library?: string | null;
  form?: string | null;
  terminated?: boolean;
  target_form?: string;
  resolution: "resolved" | "missing" | "ambiguous" | "dynamic" | "unresolved";
  candidates: string[];
  line: number;
  col: number;
  text: string;
}

export interface ProjectFinding {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  line: number | null;
  col: number | null;
  layer: string;
  hint: string | null;
  evidence: string | null;
  classification: string;
  detail: {
    file?: string; target?: string; candidates?: string[]; members?: string[];
    receiver?: string; receiver_file?: string; receiver_line?: number;
    receiver_origin?: string; via_copybooks?: string[];
    statement_line?: number; program?: string;
  } | null;
  finding_id: string;
}

// ---- cross-file data understanding (Milestone 4) ------------------------

export interface CrossFileDecl {
  file: string | null;
  name: string;
  level: number | null;
  section: string | null;
  line: number | null;
  col: number | null;
  picture: string | null;
  usage: string | null;
  byte_length: number | null;
  origin: "parsed" | "scanned";
  unsupported_clause: string | null;
}

export interface CrossFilePosition {
  position: number;
  status: "established" | "unmatched-argument" | "unmatched-parameter";
  caller?: { name: string; form: string; passing: string; passing_explicit: boolean; line: number | null; col: number | null };
  caller_decl?: CrossFileDecl | null;
  receiver?: { name: string; line: number | null; col: number | null };
  receiver_decl?: CrossFileDecl | null;
  size_caller?: number | null;
  size_receiver?: number | null;
  size_status?: "equal" | "mismatch" | "unknown";
}

export interface CrossFileMapping {
  from: string;
  to: string | null;
  target: string;
  line: number;
  col: number;
  text: string;
  status: "established" | "incomplete" | "unresolved";
  reason: string | null;
  positions: CrossFilePosition[];
}

export interface CrossFileInterface {
  file: string;
  origin: "parsed" | "scanned";
  params: { name: string; line: number | null; col: number | null; declaration: CrossFileDecl | null }[];
  copybooks: { copybook: string; via: "direct" | "nested"; chain: string[] }[];
}

export interface CrossFileSection {
  schema_note: string;
  interfaces: Record<string, CrossFileInterface>;
  mappings: CrossFileMapping[];
  copybook_declarations: Record<
    string,
    { name: string; level: number; picture: string | null; usage: string | null; byte_length: number | null; line: number; col: number; unsupported_clause: string | null }[]
  >;
  assumptions: { id: string; topic: string; detail: string }[];
  coverage: Record<string, number>;
  logical?: Record<string, LogicalModel>;
}

// ---- logical program data model (Milestone 5) ---------------------------

export interface LogicalDecl {
  decl_id: string;
  name: string;
  program: string;
  source_file: string;
  line: number | null;
  col: number | null;
  origin: "program" | "copybook";
  via_copybooks: string[];
  parent: string | null;
  parent_id: string | null;
  level: number | null;
  section: string | null;
  picture: string | null;
  usage: string | null;
  sign: string | null;
  value: string | null;
  byte_length: number | null;
  status: "established" | "partial" | "unsupported";
  unsupported_reason: string | null;
  children: string[];
  ancestor_groups: string[];
  text: string | null;
}

export interface RefCandidate {
  decl_id: string;
  name: string;
  source_file: string;
  line: number | null;
  col: number | null;
  origin: "program" | "copybook";
  via_copybooks: string[];
  byte_length: number | null;
  picture: string | null;
  usage: string | null;
  status: string;
  level: number | null;
  sign: string | null;
  value: string | null;
  unsupported_reason: string | null;
}

export interface LogicalRefRow {
  name: string;
  qualified_by: string | null;
  role: string;
  statement_line: number;
  status: "resolved" | "ambiguous" | "unresolved" | "figurative-unsupported";
  source_file?: string;
  line?: number;
  origin?: string;
  decl_status?: string;
  via_copybooks?: string[];
  decl_id?: string;
  candidates?: RefCandidate[];
}

export interface LogicalModel {
  program: string;
  declarations: LogicalDecl[];
  references: LogicalRefRow[];
  unsupported_structures: { structure: string; file: string; line: number | null; reason: string }[];
  unsupported_statements: { structure: string; file: string; line: number; reason: string; text: string }[];
  associations: { copybook: string; via: "direct" | "nested"; chain: string[] }[];
}

export interface ProjectImpact {
  file: string;
  direct_dependencies: { to: string; kind: string; line: number; evidence: string }[];
  direct_dependants: { from: string; kind: string; line: number; evidence: string }[];
  transitive_dependencies: string[];
  transitive_dependants: string[];
  unresolved_relationships: {
    kind: string; resolution: string; target: string;
    from: string; to: string | null; line: number; evidence: string;
  }[];
  data_flow: {
    sends_data_to: { with: string; target: string; line: number; status: string; evidence: string }[];
    receives_data_from: { with: string; target: string; line: number; status: string; evidence: string }[];
    unresolved_data_relationships: { with: string | null; target: string; line: number; status: string; evidence: string }[];
  };
  note: string;
}

export interface ProjectEnvelope {
  schema_version: 1 | 2;
  project: { name: string };
  files: ProjectFile[];
  skipped: { path: string; reason: string; code: string }[];
  references: Record<string, unknown>[];
  edges: ProjectEdge[];
  cycles: string[][];
  per_file: Record<string, { status: string; reason: string | null; result?: AnalysisResponse }>;
  findings: ProjectFinding[];
  cross_file?: CrossFileSection;
  coverage: Record<string, number | Record<string, number>>;
  assumptions: { id: string; topic: string; detail: string }[];
  summary: { ok: boolean; errors: number; warnings: number; infos: number; programs: number; copybooks: number };
  impact?: Record<string, ProjectImpact>;
}

export async function getExampleProject(): Promise<{ name: string; files: { path: string; content: string }[] }> {
  const res = await fetch("/api/project/example");
  if (!res.ok) await readError(res);
  return (await res.json()) as { name: string; files: { path: string; content: string }[] };
}

export async function analyzeProject(
  name: string,
  files: { path: string; content: string }[],
): Promise<ProjectEnvelope> {
  const res = await fetch("/api/project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, files }),
  });
  if (!res.ok) await readError(res);
  return (await res.json()) as ProjectEnvelope;
}
