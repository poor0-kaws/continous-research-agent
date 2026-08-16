import { ArrowUpRight, Check, FlaskConical, ShieldCheck, X } from "lucide-react";
import type { CandidateInsight, ResearchDraft } from "../types";
import { StatusBadge } from "./StatusBadge";

interface Props {
  drafts: ResearchDraft[];
  insights: CandidateInsight[];
  onVerify: (draftId: string) => void;
  onReview: (id: string, status: "useful" | "rejected") => void;
  isVerifying: boolean;
}

export function InsightPanel({ drafts, insights, onVerify, onReview, isVerifying }: Props) {
  return (
    <aside className="insight-panel" aria-label="Research and insights">
      <div className="panel-title"><span>Research desk</span><ShieldCheck size={17} /></div>

      <section className="panel-section">
        <div className="section-kicker">Browser drafts <span>{drafts.length}</span></div>
        {drafts.length === 0 && <p className="panel-empty">Browser research reports will appear here before they are trusted.</p>}
        {drafts.slice(0, 4).map((draft) => (
          <article className="draft-card" key={draft.id}>
            <div className="card-meta"><StatusBadge status={draft.status} /><time>{new Date(draft.created_at).toLocaleDateString()}</time></div>
            <p>{draft.report_text.slice(0, 240)}{draft.report_text.length > 240 ? "…" : ""}</p>
            <div className="card-actions">
              <span>{draft.cited_urls.length} approved citations</span>
              {draft.status === "pending" && (
                <button onClick={() => onVerify(draft.id)} disabled={isVerifying}>
                  Confirm evidence <ArrowUpRight size={14} />
                </button>
              )}
            </div>
          </article>
        ))}
      </section>

      <section className="panel-section">
        <div className="section-kicker">Hypotheses <span>{insights.length}</span></div>
        {insights.length === 0 && <p className="panel-empty">New patterns stay labeled as hypotheses, even when their premises are confirmed.</p>}
        {insights.slice(0, 6).map((insight) => (
          <article className="insight-card" key={insight.id}>
            <div className="insight-icon"><FlaskConical size={15} /></div>
            <div>
              <StatusBadge status={insight.verification_status} />
              <h3>{insight.title}</h3>
              <p>{insight.explanation}</p>
              <div className="insight-footer">
                <span>{insight.confidence} evidence confidence</span>
                <div>
                  <button onClick={() => onReview(insight.id, "useful")} aria-label="Mark hypothesis useful"><Check size={14} /></button>
                  <button onClick={() => onReview(insight.id, "rejected")} aria-label="Reject hypothesis"><X size={14} /></button>
                </div>
              </div>
            </div>
          </article>
        ))}
      </section>
    </aside>
  );
}
