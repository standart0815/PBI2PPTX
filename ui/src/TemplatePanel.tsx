import { useEffect, useRef, useState } from "react";
import { api, Refused } from "./api";
import { areaRect, ImageAreaFields, outsideSlide } from "./ImageAreaFields";
import { LayoutInfo, Rect, Selection, TemplateInfo } from "./types";

const LANGUAGES: { value: Selection["renderLanguage"]; label: string; sample: string }[] = [
  { value: "de-DE", label: "Deutsch", sample: "1.234,56 · 31.12.2026" },
  { value: "en-US", label: "English", sample: "1,234.56 · 12/31/2026" },
];

export function TemplatePanel({
  template,
  setTemplate,
  selection,
  setSelection,
}: {
  template: TemplateInfo | null;
  setTemplate: (t: TemplateInfo) => void;
  selection: Selection;
  setSelection: (update: (s: Selection) => Selection) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const usable = template?.layouts.filter((l) => l.usable) ?? [];
  const unusable = template?.layouts.filter((l) => !l.usable) ?? [];
  const chosen = usable.find((l) => l.name === selection.slideLayout) ?? null;

  // Keep the Selection's Slide Layout valid for this Template: keep a layout it has, otherwise
  // fall back to the recommended one (and say so when a Saved Selection asked for another).
  useEffect(() => {
    if (!template || chosen) return;
    const fallback = template.preselected ?? usable[0]?.name ?? null;
    if (selection.slideLayout === fallback) return;
    if (selection.slideLayout && fallback) {
      setNotice(`This template has no layout "${selection.slideLayout}"; using "${fallback}" instead.`);
    }
    setSelection((s) => (s.slideLayout === fallback ? s : { ...s, slideLayout: fallback }));
  }, [template, chosen, selection.slideLayout, usable, setSelection]);

  // Keep the Custom Image Area only while it fits on this Template's slides.
  useEffect(() => {
    if (!template || !selection.imageArea || !outsideSlide(selection.imageArea, template)) return;
    setNotice("Your own picture area doesn't fit on this template's slides; using the layout's area instead.");
    setSelection((s) => ({ ...s, imageArea: null }));
  }, [template, selection.imageArea, setSelection]);

  async function upload(file: File) {
    setBusy(true);
    setProblem(null);
    setNotice(null);
    try {
      setTemplate((await api.uploadTemplate(file)).template);
    } catch (e) {
      setProblem(e instanceof Refused ? e.message : `Something went wrong: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Template &amp; settings</h2>

      <div className="template-file">
        {template ? (
          <p>
            <strong>{template.fileName}</strong>{" "}
            <span className="muted small">
              {template.slideWidthCm} × {template.slideHeightCm} cm
            </span>
          </p>
        ) : (
          <p className="muted">Pick the PowerPoint template (.potx) your Deck is built from.</p>
        )}
        <button type="button" className={template ? "quiet" : ""} disabled={busy} onClick={() => fileInput.current?.click()}>
          {busy ? "Reading…" : template ? "Choose another…" : "Choose template…"}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".potx,.pptx,application/vnd.openxmlformats-officedocument.presentationml.template,application/vnd.openxmlformats-officedocument.presentationml.presentation"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) upload(file);
          }}
        />
      </div>
      {problem && <p className="error">{problem}</p>}
      {notice && <p className="info">{notice}</p>}
      {template && template.templateSlides > 0 && (
        <p className="muted small">
          The template's {template.templateSlides} example slide{template.templateSlides === 1 ? " is" : "s are"} left out of the Deck.
        </p>
      )}

      {template && (
        <div className="layout-choice">
          <fieldset className="layouts">
            <legend>Slide layout for every page</legend>
            {usable.map((layout) => (
              <label key={layout.name} className={`layout-option${layout.name === selection.slideLayout ? " chosen" : ""}`}>
                <input
                  type="radio"
                  name="slide-layout"
                  checked={layout.name === selection.slideLayout}
                  onChange={() => setSelection((s) => ({ ...s, slideLayout: layout.name }))}
                />
                <span className="layout-text">
                  <span>
                    {layout.name}
                    {layout.preselected && <span className="badge">Recommended</span>}
                  </span>
                  {layout.graphics.length > 0 && (
                    <span className="warning small">
                      ⚠ A graphic reaches into the picture area ({layout.graphics.map((g) => g.name).join(", ")}). Pages may
                      collide with it.
                    </span>
                  )}
                </span>
              </label>
            ))}
            {unusable.length > 0 && (
              <p className="muted small">Can't hold a page (no title or no room below it): {unusable.map((l) => l.name).join(", ")}</p>
            )}
          </fieldset>
          {chosen && (
            <LayoutSketch
              layout={chosen}
              aspect={template.slideHeightEmu / template.slideWidthEmu}
              area={selection.imageArea ? areaRect(selection.imageArea, template) : chosen.imageArea}
              custom={!!selection.imageArea}
            />
          )}
        </div>
      )}
      {template && chosen && (
        <ImageAreaFields
          layout={chosen}
          template={template}
          area={selection.imageArea ?? null}
          onChange={(imageArea) => setSelection((s) => ({ ...s, imageArea }))}
        />
      )}

      <fieldset className="languages">
        <legend>Filters on slides</legend>
        <label className="language-option">
          <input
            type="checkbox"
            checked={selection.showFilters ?? false}
            onChange={(e) => setSelection((s) => ({ ...s, showFilters: e.target.checked }))}
          />
          Show Filters on slides
          <span className="muted small">a box to the right of each page that has Filters</span>
        </label>
      </fieldset>

      <fieldset className="languages">
        <legend>Render language: numbers and dates in the pages</legend>
        {LANGUAGES.map((l) => (
          <label key={l.value} className="language-option">
            <input
              type="radio"
              name="render-language"
              checked={selection.renderLanguage === l.value}
              onChange={() => setSelection((s) => ({ ...s, renderLanguage: l.value }))}
            />
            {l.label} <span className="muted small">{l.sample}</span>
          </label>
        ))}
      </fieldset>
    </section>
  );
}

// A sketch of a Slide Layout: title and footers grey, the picture area dashed, colliding graphics red.
function LayoutSketch({ layout, aspect, area, custom }: { layout: LayoutInfo; aspect: number; area: Rect | null; custom: boolean }) {
  const W = 320;
  const H = Math.round(W * aspect);
  const r = (rect: Rect) => ({ x: rect.x * W, y: rect.y * H, width: rect.w * W, height: rect.h * H });
  return (
    <figure className="sketch">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Sketch of the layout ${layout.name}`}>
        <rect className="sk-slide" x={0.5} y={0.5} width={W - 1} height={H - 1} />
        {layout.title && <rect className="sk-title" {...r(layout.title)} />}
        {layout.footers.map((f, i) => (
          <rect key={i} className="sk-footer" {...r(f)} />
        ))}
        {area && <rect className="sk-area" {...r(area)} />}
        {layout.graphics.map((g) => (
          <rect key={g.name} className="sk-graphic" {...r(g)} />
        ))}
      </svg>
      <figcaption className="muted small">
        Pages go into the dashed area{custom && " (your own)"}, as large as possible, from the top left.
        {layout.graphics.length > 0 && " Red: graphics in the way."}
      </figcaption>
    </figure>
  );
}
