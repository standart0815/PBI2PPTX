import { useState } from "react";
import { api, Refused } from "./api";
import { FilterEditor } from "./FilterEditor";
import { describeFilter, limitWarning } from "./filters";
import { Entry, Filter, reachedThrough } from "./types";

export function EntryItem({
  entry,
  position,
  count,
  canDuplicate,
  onChange,
  onMove,
  onDuplicate,
  onRemove,
  onApplyFilterToAll,
  canUseWindow,
  drag,
}: {
  entry: Entry;
  position: number;
  count: number;
  canDuplicate: boolean;
  onChange: (entry: Entry) => void;
  onMove: (to: number) => void;
  onDuplicate: () => void;
  onRemove: () => void;
  onApplyFilterToAll: (filter: Filter) => void;
  canUseWindow: boolean; // signed in, and no Export running

  drag: {
    onDragStart: () => void;
    onDragOver: (e: React.DragEvent) => void;
    onDrop: () => void;
    onDragEnd: () => void;
    over: boolean;
  };
}) {
  const [showFilters, setShowFilters] = useState(false);
  const [opened, setOpened] = useState<{ ok: boolean; text: string } | null>(null);
  const warning = limitWarning(entry);

  async function open(withFilters: boolean) {
    setOpened(null);
    try {
      await api.openPage(entry.pageUrl, withFilters ? entry.filters : []);
      setOpened({
        ok: true,
        text: withFilters
          ? "Opened in the Power BI Window with its Filters. Your own slicer selections may still show there; the slide shows the page reset to its default state."
          : "Opened in the Power BI Window, without Filters.",
      });
    } catch (e) {
      setOpened({ ok: false, text: e instanceof Refused ? e.message : `Something went wrong: ${String(e)}` });
    }
  }

  return (
    <li
      className={`entry${drag.over ? " drag-over" : ""}`}
      draggable
      onDragStart={drag.onDragStart}
      onDragOver={drag.onDragOver}
      onDrop={drag.onDrop}
      onDragEnd={drag.onDragEnd}
    >
      <div className="entry-main">
        <span className="handle" title="Drag to reorder" aria-hidden="true">
          ⋮⋮
        </span>
        <span className="position">{position + 1}</span>
        <div className="entry-body">
          <input
            className="title-input"
            aria-label={`Slide title of Entry ${position + 1}`}
            value={entry.slideTitle}
            onChange={(e) => onChange({ ...entry, slideTitle: e.target.value })}
            onBlur={() => !entry.slideTitle.trim() && onChange({ ...entry, slideTitle: entry.pageName })}
          />
          <p className="muted small">
            {entry.pageName}
            {entry.reportName && ` · ${entry.reportName}`} · {reachedThrough(entry.pageUrl)}
          </p>
          {warning && <p className="warning small">{warning}</p>}
          {opened && <p className={`small ${opened.ok ? "muted" : "error"}`}>{opened.text}</p>}
          {entry.filters.length > 0 && (
            <p className="small chips">
              {entry.filters.map((f, i) => (
                <span key={i} className="chip">
                  {describeFilter(f)}
                </span>
              ))}
            </p>
          )}
        </div>
        <div className="entry-actions">
          <button
            type="button"
            className="quiet"
            disabled={!canUseWindow}
            title="Show this page in the Power BI Window, without Filters"
            onClick={() => open(false)}
          >
            Open
          </button>
          {entry.filters.length > 0 && (
            <button
              type="button"
              className="quiet"
              disabled={!canUseWindow}
              title="Show this page in the Power BI Window, with this Entry's Filters"
              onClick={() => open(true)}
            >
              Open with Filters
            </button>
          )}
          <button type="button" className="quiet" aria-expanded={showFilters} onClick={() => setShowFilters(!showFilters)}>
            Filters{entry.filters.length ? ` (${entry.filters.length})` : ""}
          </button>
          <button type="button" className="quiet icon" aria-label="Move up" disabled={position === 0} onClick={() => onMove(position - 1)}>
            ↑
          </button>
          <button
            type="button"
            className="quiet icon"
            aria-label="Move down"
            disabled={position === count - 1}
            onClick={() => onMove(position + 1)}
          >
            ↓
          </button>
          <button type="button" className="quiet" disabled={!canDuplicate} onClick={onDuplicate}>
            Duplicate
          </button>
          <button type="button" className="quiet danger" onClick={onRemove}>
            Remove
          </button>
        </div>
      </div>
      {showFilters && (
        <FilterEditor
          filters={entry.filters}
          onChange={(filters) => onChange({ ...entry, filters })}
          onApplyToAll={onApplyFilterToAll}
          onCheck={canUseWindow ? (f) => api.checkFilter(entry.pageUrl, f) : null}
        />
      )}
    </li>
  );
}
