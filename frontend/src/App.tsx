import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock3, Play, RefreshCw, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import { InsightPanel } from "./components/InsightPanel";
import { KnowledgeGraph } from "./components/KnowledgeGraph";
import { SourceCatalogDrawer } from "./components/SourceCatalogDrawer";
import { TopicSidebar } from "./components/TopicSidebar";

export default function App() {
  const queryClient = useQueryClient();
  const topicsQuery = useQuery({ queryKey: ["topics"], queryFn: api.listTopics });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [showSources, setShowSources] = useState(false);

  useEffect(() => {
    if (!selectedId && topicsQuery.data?.length) setSelectedId(topicsQuery.data[0].id);
  }, [selectedId, topicsQuery.data]);

  const selectedTopic = topicsQuery.data?.find((topic) => topic.id === selectedId) ?? null;
  const graphQuery = useQuery({
    queryKey: ["graph", selectedId],
    queryFn: () => api.getGraph(selectedId!),
    enabled: Boolean(selectedId),
  });
  const draftsQuery = useQuery({
    queryKey: ["drafts", selectedId],
    queryFn: () => api.listDrafts(selectedId!),
    enabled: Boolean(selectedId),
  });
  const insightsQuery = useQuery({
    queryKey: ["insights", selectedId],
    queryFn: () => api.listInsights(selectedId!),
    enabled: Boolean(selectedId),
  });
  const runQuery = useQuery({
    queryKey: ["run", activeRunId],
    queryFn: () => api.getRun(activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2_000 : false;
    },
  });
  const sourcesQuery = useQuery({
    queryKey: ["sources"],
    queryFn: api.listSources,
    enabled: showSources,
  });

  useEffect(() => {
    if (runQuery.data?.status !== "completed") return;
    queryClient.invalidateQueries({ queryKey: ["drafts", selectedId] });
    queryClient.invalidateQueries({ queryKey: ["graph", selectedId] });
    queryClient.invalidateQueries({ queryKey: ["insights", selectedId] });
  }, [queryClient, runQuery.data?.status, selectedId]);

  const createTopic = useMutation({
    mutationFn: api.createTopic,
    onSuccess: (topic) => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      setSelectedId(topic.id);
    },
  });
  const startRun = useMutation({
    mutationFn: (topicId: string) => api.startRun(topicId),
    onSuccess: (run) => setActiveRunId(run.id),
  });
  const verifyDraft = useMutation({
    mutationFn: api.verifyDraft,
    onSuccess: (run) => setActiveRunId(run.id),
  });
  const reviewInsight = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "useful" | "rejected" }) => api.reviewInsight(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["insights", selectedId] }),
  });
  const toggleSource = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => api.setSourceEnabled(id, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources"] }),
  });

  const runIsActive = runQuery.data?.status === "queued" || runQuery.data?.status === "running";

  return (
    <div className="app-shell">
      <TopicSidebar
        topics={topicsQuery.data ?? []}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onCreate={(value) => createTopic.mutate(value)}
        isCreating={createTopic.isPending}
        onOpenSources={() => setShowSources(true)}
      />

      <main className="workspace">
        <header className="workspace-header">
          <div>
            <span className="eyebrow">Knowledge graph</span>
            <h1>{selectedTopic?.title ?? "Choose a research topic"}</h1>
            {selectedTopic && <p>{selectedTopic.question}</p>}
          </div>
          <div className="header-actions">
            {selectedTopic?.next_run_at && (
              <span className="schedule"><Clock3 size={14} /> Next daily run {new Date(selectedTopic.next_run_at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric" })}</span>
            )}
            <button
              className="run-button"
              disabled={!selectedId || startRun.isPending || runIsActive}
              onClick={() => selectedId && startRun.mutate(selectedId)}
            >
              {runIsActive ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}
              {runIsActive ? runQuery.data?.progress_stage.replaceAll("_", " ") : "Run research"}
            </button>
          </div>
        </header>

        {runQuery.data?.status === "failed" && (
          <div className="error-banner"><ShieldAlert size={17} /> Research stopped safely: {runQuery.data.error_message}</div>
        )}

        <section className="graph-stage" aria-label="Topic knowledge graph">
          <div className="graph-legend">
            <span><i className="legend-dot legend-dot--claim" /> Confirmed claim</span>
            <span><i className="legend-dot legend-dot--concept" /> Concept</span>
            <span><i className="legend-dot legend-dot--hypothesis" /> Hypothesis</span>
          </div>
          <KnowledgeGraph graph={graphQuery.data ?? { nodes: [], edges: [] }} />
        </section>
      </main>

      <InsightPanel
        drafts={draftsQuery.data ?? []}
        insights={insightsQuery.data ?? []}
        onVerify={(id) => verifyDraft.mutate(id)}
        onReview={(id, status) => reviewInsight.mutate({ id, status })}
        isVerifying={verifyDraft.isPending}
      />
      {showSources && (
        <SourceCatalogDrawer
          sources={sourcesQuery.data ?? []}
          onClose={() => setShowSources(false)}
          onToggle={(id, enabled) => toggleSource.mutate({ id, enabled })}
        />
      )}
    </div>
  );
}
