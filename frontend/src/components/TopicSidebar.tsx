import { Plus, Radar, Search, Settings2 } from "lucide-react";
import { FormEvent, useState } from "react";
import type { Topic } from "../types";

interface Props {
  topics: Topic[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: (value: { title: string; question: string; keywords: string[] }) => void;
  isCreating: boolean;
  onOpenSources: () => void;
}

export function TopicSidebar({ topics, selectedId, onSelect, onCreate, isCreating, onOpenSources }: Props) {
  const [showForm, setShowForm] = useState(false);
  const [topicFilter, setTopicFilter] = useState("");
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [keywords, setKeywords] = useState("");
  const visibleTopics = topics.filter((topic) => {
    const searchableText = [topic.title, topic.question, ...topic.keywords].join(" ").toLowerCase();
    return searchableText.includes(topicFilter.toLowerCase().trim());
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !question.trim()) return;
    onCreate({
      title: title.trim(),
      question: question.trim(),
      keywords: keywords.split(",").map((item) => item.trim()).filter(Boolean),
    });
    setTitle("");
    setQuestion("");
    setKeywords("");
    setShowForm(false);
  }

  return (
    <aside className="topic-sidebar" aria-label="Research topics">
      <div className="brand">
        <span className="brand-mark"><Radar size={18} /></span>
        <div><strong>ContResAI</strong><small>Evidence workspace</small></div>
      </div>

      <div className="search-shell">
        <Search size={15} />
        <input
          aria-label="Filter topics"
          placeholder="Find a topic"
          value={topicFilter}
          onChange={(event) => setTopicFilter(event.target.value)}
        />
      </div>

      <div className="sidebar-heading">
        <span>Research topics</span>
        <button className="icon-button" onClick={() => setShowForm((value) => !value)} aria-label="Create topic">
          <Plus size={16} />
        </button>
      </div>

      {showForm && (
        <form className="topic-form" onSubmit={submit}>
          <label>Short name<input value={title} onChange={(event) => setTitle(event.target.value)} minLength={3} required /></label>
          <label>Research question<textarea value={question} onChange={(event) => setQuestion(event.target.value)} minLength={10} required /></label>
          <label>Keywords<input value={keywords} onChange={(event) => setKeywords(event.target.value)} placeholder="energy, batteries" /></label>
          <button className="primary-button" disabled={isCreating}>{isCreating ? "Creating…" : "Create topic"}</button>
        </form>
      )}

      <nav className="topic-list">
        {visibleTopics.map((topic) => (
          <button
            key={topic.id}
            className={topic.id === selectedId ? "topic-item topic-item--active" : "topic-item"}
            onClick={() => onSelect(topic.id)}
          >
            <span className="topic-dot" />
            <span><strong>{topic.title}</strong><small>{topic.keywords.slice(0, 3).join(" · ") || "New research topic"}</small></span>
          </button>
        ))}
      </nav>

      <button className="sidebar-footnote" onClick={onOpenSources}>
        <span className="safe-dot" />
        <span><strong>Guarded browsing</strong><small>112 reviewed source rules</small></span>
        <Settings2 size={14} />
      </button>
    </aside>
  );
}
