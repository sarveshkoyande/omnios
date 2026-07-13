import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import Box from "@mui/material/Box";
import { planDocSkinCss } from "./planDocSkinCss";
import { domToMarkdown, isRiskyCell } from "./planMarkdown";

let styleInjected = false;
function ensureSkinStyle() {
  if (styleInjected) return;
  const tag = document.createElement("style");
  tag.setAttribute("data-plan-doc-skin", "true");
  tag.textContent = planDocSkinCss;
  document.head.appendChild(tag);
  styleInjected = true;
}

export interface PlanDocumentHandle {
  /** Reads the live (possibly edited) DOM and derives {html, markdown} for saving. */
  getEditedContent: () => { html: string; markdown: string };
  /** Discards in-progress edits by re-painting the last-saved html prop. */
  revert: () => void;
}

/**
 * Renders the server-composed Brand Engagement Plan HTML (see planDocSkinCss.ts
 * for why this is injected HTML rather than ~25 discrete React components).
 * Sections are native <details>/<summary> — collapse/expand needs no JS. This
 * only replicates the legacy TOC behavior of opening a section before scrolling
 * to it, and — when `editing` is true — makes text nodes directly editable the
 * same way the legacy plan panel did (contenteditable on headings/paragraphs/
 * list items/plain table cells), so a parent Save button can pull the edited
 * DOM back out via the ref.
 */
export const PlanDocument = forwardRef<PlanDocumentHandle, { html: string; editing?: boolean }>(
  function PlanDocument({ html, editing = false }, ref) {
    const rootRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      ensureSkinStyle();
    }, []);

    useEffect(() => {
      const root = rootRef.current;
      if (!root) return;
      const onClick = (e: Event) => {
        const a = (e.target as HTMLElement)?.closest("a[href^='#']") as HTMLAnchorElement | null;
        if (!a) return;
        const id = a.getAttribute("href")?.slice(1);
        if (!id) return;
        const target = document.getElementById(id);
        if (target && target.tagName === "DETAILS") (target as HTMLDetailsElement).open = true;
      };
      root.addEventListener("click", onClick);

      const fresh = root.querySelector(".sec-fresh");
      if (fresh) fresh.scrollIntoView({ behavior: "smooth", block: "start" });

      return () => root.removeEventListener("click", onClick);
    }, [html]);

    useEffect(() => {
      const root = rootRef.current;
      if (!root) return;
      if (editing) {
        root.querySelectorAll("details").forEach((d) => { (d as HTMLDetailsElement).open = true; });
        root.querySelectorAll("p, li, h1, h2, h3, h4, figcaption").forEach((el) => el.setAttribute("contenteditable", "true"));
        root.querySelectorAll("td, th").forEach((cell) => {
          if (!isRiskyCell(cell)) cell.setAttribute("contenteditable", "true");
        });
      } else {
        root.querySelectorAll('[contenteditable="true"]').forEach((el) => el.removeAttribute("contenteditable"));
      }
    }, [editing]);

    useImperativeHandle(ref, () => ({
      getEditedContent: () => {
        const root = rootRef.current;
        if (!root) return { html: "", markdown: "" };
        const clone = root.cloneNode(true) as HTMLElement;
        clone.querySelectorAll("[contenteditable]").forEach((el) => el.removeAttribute("contenteditable"));
        return { html: clone.innerHTML, markdown: domToMarkdown(clone) };
      },
      revert: () => {
        const root = rootRef.current;
        if (root) root.innerHTML = html;
      },
    }));

    return <Box ref={rootRef} className="plan-doc-skin" dangerouslySetInnerHTML={{ __html: html }} />;
  },
);
