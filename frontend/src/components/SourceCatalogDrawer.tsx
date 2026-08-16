import { Search, ShieldCheck, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { SourceCatalogEntry } from "../types";

interface Props {
  sources: SourceCatalogEntry[];
  onClose: () => void;
  onToggle: (id: string, enabled: boolean) => void;
}

export function SourceCatalogDrawer({ sources, onClose, onToggle }: Props) {
  const [query, setQuery] = useState("");
  const visibleSources = useMemo(() => {
    const normalized = query.toLowerCase().trim();
    if (!normalized) return sources;
    return sources.filter((source) =>
      [source.publisher, source.hostname, source.category, ...source.topic_tags]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [query, sources]);

  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="source-drawer" role="dialog" aria-modal="true" aria-labelledby="source-title" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div><span className="eyebrow">Trust boundary</span><h2 id="source-title">Approved source catalog</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="Close source catalog"><X size={16} /></button>
        </header>
        <p className="drawer-intro">The browser agent can search only enabled exact hosts. Paywalled sources can suggest leads, but they cannot provide evidence.</p>
        <label className="source-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search 112 reviewed rules" /></label>
        <div className="source-count"><ShieldCheck size={14} /> {visibleSources.filter((source) => source.is_enabled).length} enabled sources</div>
        <div className="source-list">
          {visibleSources.map((source) => (
            <article className="source-row" key={source.id}>
              <div>
                <strong>{source.publisher}</strong>
                <small>{source.hostname} · {source.category.replaceAll("-", " ")}</small>
                <p>{source.approval_reason}</p>
                <span className={`access-pill access-pill--${source.access_mode}`}>{source.access_mode.replaceAll("_", " ")}</span>
              </div>
              <label className="toggle">
                <input type="checkbox" checked={source.is_enabled} onChange={(event) => onToggle(source.id, event.target.checked)} aria-label={`Enable ${source.publisher}`} />
                <span />
              </label>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
