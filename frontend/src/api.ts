import type {
  CandidateInsight,
  GraphData,
  ResearchDraft,
  ResearchRun,
  SourceCatalogEntry,
  Topic,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

export const api = {
  listTopics: () => request<Topic[]>("/topics"),
  createTopic: (payload: { title: string; question: string; keywords: string[] }) =>
    request<Topic>("/topics", { method: "POST", body: JSON.stringify(payload) }),
  startRun: (topicId: string) =>
    request<ResearchRun>(`/topics/${topicId}/runs`, { method: "POST" }),
  getRun: (runId: string) => request<ResearchRun>(`/runs/${runId}`),
  listDrafts: (topicId: string) =>
    request<ResearchDraft[]>(`/topics/${topicId}/research-drafts`),
  verifyDraft: (draftId: string) =>
    request<ResearchRun>(`/research-drafts/${draftId}/verify`, { method: "POST" }),
  listInsights: (topicId: string) =>
    request<CandidateInsight[]>(`/topics/${topicId}/candidate-insights`),
  reviewInsight: (insightId: string, review_status: "useful" | "rejected") =>
    request<CandidateInsight>(`/candidate-insights/${insightId}`, {
      method: "PATCH",
      body: JSON.stringify({ review_status }),
    }),
  getGraph: (topicId: string) => request<GraphData>(`/topics/${topicId}/graph`),
  listSources: () => request<SourceCatalogEntry[]>("/source-catalog"),
  setSourceEnabled: (sourceId: string, is_enabled: boolean) =>
    request<SourceCatalogEntry>(`/source-catalog/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify({ is_enabled }),
    }),
};
