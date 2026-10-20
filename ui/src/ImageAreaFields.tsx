import { useEffect, useState } from "react";
import { CustomImageArea, LayoutInfo, Rect, TemplateInfo } from "./types";

const EMU_PER_CM = 360_000;
const SLACK_CM = 0.05; // as pbi2pptx/template.py: the fields round to hundredths of a cm
const FIELDS: { key: keyof CustomImageArea; label: string }[] = [
  { key: "left", label: "Left" },
  { key: "top", label: "Top" },
  { key: "width", label: "Max. width" },
  { key: "height", label: "Max. height" },
];

const round = (cm: number) => Math.round(cm * 100) / 100;

type Texts = Record<keyof CustomImageArea, string>;
const number = (text: string) => round(Number(text.trim().replace(",", ".") || NaN));
const parse = (t: Texts): CustomImageArea => ({ left: number(t.left), top: number(t.top), width: number(t.width), height: number(t.height) });
const same = (a: CustomImageArea, b: CustomImageArea) => FIELDS.every(({ key }) => a[key] === b[key]);

export function slideCm(template: TemplateInfo) {
  return { width: template.slideWidthEmu / EMU_PER_CM, height: template.slideHeightEmu / EMU_PER_CM };
}

/** The Slide Layout's own Image Area, in cm. */
export function layoutArea(layout: LayoutInfo, template: TemplateInfo): CustomImageArea | null {
  const r = layout.imageArea;
  if (!r) return null;
  const slide = slideCm(template);
  return { left: round(r.x * slide.width), top: round(r.y * slide.height), width: round(r.w * slide.width), height: round(r.h * slide.height) };
}

/** Why the area can't be used on this slide, or null when it fits. */
export function outsideSlide(area: CustomImageArea, template: TemplateInfo): string | null {
  const slide = slideCm(template);
  if (![area.left, area.top, area.width, area.height].every(Number.isFinite)) return "Enter a number in every field.";
  if (area.width <= 0 || area.height <= 0) return "The width and the height must be more than 0.";
  if (area.left < 0 || area.top < 0) return "Left and top start at 0, the slide's top-left corner.";
  if (area.left + area.width > slide.width + SLACK_CM || area.top + area.height > slide.height + SLACK_CM) {
    return `This reaches outside the slide (${round(slide.width)} × ${round(slide.height)} cm).`;
  }
  return null;
}

/** The area as a fraction of the slide, the way the layout geometry comes from the server. */
export function areaRect(area: CustomImageArea, template: TemplateInfo): Rect {
  const slide = slideCm(template);
  return { x: area.left / slide.width, y: area.top / slide.height, w: area.width / slide.width, h: area.height / slide.height };
}

const overlaps = (a: Rect, b: Rect) => !(b.x + b.w <= a.x || b.x >= a.x + a.w || b.y + b.h <= a.y || b.y >= a.y + a.h);

/** What the Custom Image Area reaches into: the title, the footers, Decorative Graphics. */
export function overlapWarning(area: CustomImageArea, layout: LayoutInfo, template: TemplateInfo): string | null {
  const rect = areaRect(area, template);
  const hits = [
    ...(layout.title && overlaps(rect, layout.title) ? ["the title"] : []),
    ...(layout.footers.some((f) => overlaps(rect, f)) ? ["the footers"] : []),
    ...layout.graphics.filter((g) => overlaps(rect, g)).map((g) => g.name),
  ];
  return hits.length ? `⚠ The picture area reaches into ${hits.join(", ")}. Pages may cover it.` : null;
}

export function ImageAreaFields({
  layout,
  template,
  area,
  onChange,
}: {
  layout: LayoutInfo;
  template: TemplateInfo;
  area: CustomImageArea | null; // null: the layout's own
  onChange: (area: CustomImageArea | null) => void;
}) {
  const shown = area ?? layoutArea(layout, template);
  // What the User is typing, kept until it makes an area that fits on the slide.
  const [draft, setDraft] = useState<Texts | null>(null);
  // Another area arrived (a Saved Selection, "Back to the layout's area", another layout): show it.
  useEffect(() => setDraft((d) => (d && area && same(parse(d), area) ? d : null)), [area, layout.name, template]);
  if (!shown) return null;

  const texts = draft ?? (Object.fromEntries(FIELDS.map(({ key }) => [key, String(shown[key])])) as Texts);
  const problem = draft ? outsideSlide(parse(draft), template) : null;
  const warning = !problem && area ? overlapWarning(area, layout, template) : null;

  function edit(key: keyof CustomImageArea, text: string) {
    const next = { ...texts, [key]: text };
    setDraft(next);
    const typed = parse(next);
    if (!outsideSlide(typed, template)) onChange(typed);
  }

  return (
    <fieldset className="image-area">
      <legend>Picture area (cm, from the slide's top-left corner)</legend>
      <div className="image-area-fields">
        {FIELDS.map(({ key, label }) => (
          <label key={key}>
            <span className="small">{label}</span>
            <input type="text" inputMode="decimal" value={texts[key]} onChange={(e) => edit(key, e.target.value)} />
          </label>
        ))}
      </div>
      {problem && <p className="error small">{problem}</p>}
      {warning && <p className="warning small">{warning}</p>}
      <p className="muted small">
        {area ? "Your own picture area, for every page." : "The layout's own picture area. Change a value to set your own."}{" "}
        {area && (
          <button type="button" className="quiet" onClick={() => onChange(null)}>
            Back to the layout's area
          </button>
        )}
      </p>
    </fieldset>
  );
}
