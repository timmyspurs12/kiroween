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
  dataflow?: {
    schema_note: string;
    programs: Record<string, DataflowProgram>;
    cross_program_links: CrossProgramLink[];
    assumptions: { id: string; topic: string; detail: string }[];
    coverage: Record<string, number>;
  };
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

// ---- statement-level data flow (Milestone 6) ----------------------------

export interface FlowDecl {
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

export interface FlowOperand {
  role: string;
  kind: string;
  name?: string;
  parent?: string | null;
  text?: string;
  resolution?: string;
  decl?: FlowDecl;
  candidates?: RefCandidate[];
}

export interface DataflowOp {
  op_id: string;
  program: string;
  source_file: string;
  line: number;
  col: number;
  type: "MOVE" | "COMPUTE" | "ADD" | "SUBTRACT" | "MULTIPLY" | "DIVIDE";
  origin: "parsed" | "scanned";
  status: "established" | "partial" | "unresolved" | "unsupported";
  source_operands: FlowOperand[];
  receivers: FlowOperand[];
  options: {
    rounded: boolean; size_error: boolean; mode: string | null;
    giving: boolean; remainder: string | null;
  };
  guards: { cond_id: string; branch: string; line: number }[];
  evidence: string;
  expression?: { text: string; supported: boolean } | null;
  unsupported_reason?: string | null;
}

export interface DataflowCondition {
  cond_id: string;
  program: string;
  source_file: string;
  line: number;
  col: number;
  op: string | null;
  left: FlowOperand;
  right: FlowOperand;
  origin: string;
  evidence: string;
  status: string;
}

// ---- decision paths (Milestone 7) ----------------------------------------

export interface DecisionConvergence {
  kind: "operation" | "scope-end";
  op_id: string | null;
  line: number;
  evidence: string;
}

export interface DecisionSummary {
  condition: string | null;
  then: string[];
  else: string[] | null;
  after: string | null;
}

export interface DecisionRecord {
  decision_id: string;
  program: string;
  source_file: string;
  line: number;
  col: number;
  origin: "parsed" | "scanned";
  condition_id: string;
  has_else: boolean;
  then_ops: string[];
  else_ops: string[];
  nested_decisions: string[];
  parent_decision: string | null;
  end_line: number;
  convergence: DecisionConvergence | null;
  status: string;
  evidence: string;
  summary: DecisionSummary;
  then_lines?: number[];
  else_lines?: number[];
}

export interface DataflowProgram {
  program: string;
  origin: "parsed" | "scanned";
  operations: DataflowOp[];
  conditions: DataflowCondition[];
  decisions?: DecisionRecord[];
  sequence?: string[];
  rules?: RulesSection;
  graph: { nodes: FlowNode[]; edges: FlowEdge[] };
  unsupported_statements: { structure: string; file: string; line: number; reason: string; text: string }[];
  coverage: Record<string, number>;
}

// ---- rule candidates (Milestone 8) ----------------------------------------

export interface RuleItem {
  name?: string | null;
  text?: string | null;
  kind?: string | null;
  role?: string;
  resolution?: string | null;
  decl?: FlowDecl;
  candidates?: RefCandidate[];
  side?: string;
  source_file?: string | null;
  line?: number | null;
  origin?: string | null;
  via_copybooks?: string[];
}

export interface RuleOpRef {
  op_id: string;
  type: string;
  line: number;
  col: number;
  status: string;
  evidence: string;
  summary: string | null;
  reads: { name?: string | null; text?: string | null; kind?: string | null; resolution?: string | null }[];
  writes: { name?: string | null; resolution?: string | null }[];
}

export interface RuleCrossProgram {
  callee: string;
  argument: string | null;
  parameter: string | null;
  call_line: number;
  call_evidence: string;
  status: string;
  mapping_status: string | null;
  position: number | null;
  written_by_op: string;
  callee_reads: { op_id: string; line: number; evidence: string }[];
  reason?: string | null;
  qualification?: string | null;
}

export interface RuleCandidate {
  rule_id: string;
  program: string;
  source_file: string;
  line: number;
  end_line: number | null;
  origin: string;
  decision_id: string;
  condition_id: string;
  condition_text: string;
  condition_operands: RuleItem[];
  has_else: boolean;
  then_ops: string[];
  else_ops: string[];
  items_read: RuleItem[];
  items_written: RuleItem[];
  downstream_uses: { via_item: string; op_id: string; label: string | null; line: number | null; evidence: string | null }[];
  cross_program: RuleCrossProgram[];
  unresolved_elements: { element: string; detail: string; line: number }[];
  status: "established_structure" | "partial";
  explanation: string;
  trace: {
    condition_line: number | null;
    condition_evidence: string | null;
    op_ids: string[];
    decl_ids: string[];
    summary: DecisionSummary;
  };
}

export interface RuleUnsupported {
  rule_id: string;
  program: string;
  source_file: string;
  line: number | null;
  structure: string;
  status: "unsupported";
  reason: string;
  evidence: string;
}

export interface RulesSection {
  program: string;
  candidates: RuleCandidate[];
  unsupported: RuleUnsupported[];
  coverage: Record<string, number>;
}

export interface FlowNode {
  id: string; kind: string; ref: string | null; label: string;
  origin: string; source_file: string; line: number | null;
}

export interface FlowEdge {
  from: string; to: string; kind: string; role?: string | null;
  line: number; evidence: string; rounded?: boolean;
}

export interface CrossProgramLink {
  caller: string; callee: string;
  argument: string | null; parameter: string | null;
  call: { target: string; line: number; evidence: string };
  mapping_status: string;
  position: number | null;
  status: "established" | "unresolved_declaration";
  from_decl: string | null; to_decl: string | null;
  reason?: string;
  caller_writes: { op_id: string; line: number; evidence: string }[];
  callee_reads: { op_id: string; line: number; evidence: string }[];
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
