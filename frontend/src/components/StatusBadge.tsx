import type { KnowledgeStatus } from "../types";

const LABELS: Record<string, string> = {
  pending: "Pending check",
  confirmed: "Confirmed evidence",
  partially_confirmed: "Partially confirmed",
  contested: "Sources disagree",
  unverified: "Unverified",
  rejected: "Rejected",
};

export function StatusBadge({ status }: { status: KnowledgeStatus | string }) {
  return <span className={`status status--${status}`}>{LABELS[status] ?? status}</span>;
}
