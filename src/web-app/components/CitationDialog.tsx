"use client";

import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useCitationDialog } from "./CitationDialogContext";
import { getCitationMarkdownContent } from "./chatMessageTransforms";
import { SearchCitationEnrichmentResponse, SearchCitationResult } from "../lib/types";

type EnrichmentState = {
  citation?: SearchCitationResult;
  status: "idle" | "loading" | "ready" | "stale" | "missing" | "error";
};

function mergeCitation(base: SearchCitationResult, override?: SearchCitationResult): SearchCitationResult {
  return override ? { ...base, ...override } : base;
}

const dialogMarkdownComponents: Components = {
  a: ({ node, href, children, ...props }) => {
    const isInPageLink = typeof href === "string" && href.startsWith("#");
    return (
      <a
        {...props}
        href={href}
        {...(isInPageLink ? {} : { rel: "noreferrer", target: "_blank" })}
      >
        {children}
      </a>
    );
  },
  table: ({ node, className, children, ...props }) => (
    <div className="citationTableWrapper">
      <table {...props} className={className ? `citationTable ${className}` : "citationTable"}>
        {children}
      </table>
    </div>
  ),
  img: ({ node, alt, className, ...props }) => (
    <img
      {...props}
      alt={alt ?? ""}
      className={className ? `citationImage citationMarkdownImage ${className}` : "citationImage citationMarkdownImage"}
      loading="lazy"
    />
  ),
};

export function CitationDialog() {
  const { openRefNumber, closeCitation, getCitation } = useCitationDialog();
  const [enrichment, setEnrichment] = useState<EnrichmentState>({ status: "idle" });
  const overlayRef = useRef<HTMLDivElement>(null);
  const previousRefNumber = useRef<number | null>(null);

  const entry = openRefNumber !== null ? getCitation(openRefNumber) : undefined;

  const loadEnrichment = useCallback(async (threadId: string, toolCallId: string, refNumber: number) => {
    setEnrichment({ status: "loading" });
    try {
      const response = await fetch(
        `/api/conversations/${encodeURIComponent(threadId)}/citations/${encodeURIComponent(toolCallId)}/${encodeURIComponent(String(refNumber))}`,
        { cache: "no-store" },
      );
      let payload: SearchCitationEnrichmentResponse = { status: "missing" };
      if (response.ok) {
        payload = (await response.json()) as SearchCitationEnrichmentResponse;
      }
      startTransition(() => {
        setEnrichment({
          citation: payload.citation,
          status: payload.status === "ready" || payload.status === "stale" ? payload.status : "missing",
        });
      });
    } catch {
      startTransition(() => {
        setEnrichment({ status: "error" });
      });
    }
  }, []);

  useEffect(() => {
    if (openRefNumber === null || !entry) {
      previousRefNumber.current = null;
      return;
    }

    if (openRefNumber === previousRefNumber.current) {
      return;
    }

    previousRefNumber.current = openRefNumber;
    setEnrichment({ status: "idle" });

    const needsEnrichment =
      entry.threadId &&
      entry.toolCallId &&
      entry.citation.chunk_id &&
      entry.citation.content_source !== "full";

    if (needsEnrichment) {
      void loadEnrichment(entry.threadId!, entry.toolCallId!, openRefNumber);
    }
  }, [openRefNumber, entry, loadEnrichment]);

  useEffect(() => {
    if (openRefNumber === null) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeCitation();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [openRefNumber, closeCitation]);

  if (openRefNumber === null || !entry) {
    return null;
  }

  const { citation } = entry;
  const displayCitation = mergeCitation(citation, enrichment.citation);
  const refLabel = `Ref #${openRefNumber}`;
  const title = displayCitation.title ?? displayCitation.section_header ?? "Reference";

  const hasFull = enrichment.status === "ready" || enrichment.status === "stale" || displayCitation.content_source === "full";
  const content = hasFull
    ? displayCitation.content ?? displayCitation.summary ?? ""
    : displayCitation.summary ?? displayCitation.content ?? "";
  const markdownContent = getCitationMarkdownContent(content, displayCitation, [displayCitation]);

  return (
    <div
      className="citationDialogOverlay"
      ref={overlayRef}
      onClick={(event) => {
        if (event.target === overlayRef.current) {
          closeCitation();
        }
      }}
      role="dialog"
      aria-modal="true"
      aria-label={`${refLabel}: ${title}`}
    >
      <div className="citationDialogPanel">
        <div className="citationDialogHeader">
          <div className="citationDialogHeaderLeft">
            <span className="citationBadge">{refLabel}</span>
            <strong className="citationDialogTitle">{title}</strong>
            {displayCitation.section_header && displayCitation.section_header !== title ? (
              <span className="citationDialogSection">{displayCitation.section_header}</span>
            ) : null}
          </div>
          <button
            className="citationDialogClose"
            onClick={closeCitation}
            type="button"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="citationDialogBody">
          {enrichment.status === "loading" ? (
            <p className="citationStatus" role="status">Loading source excerpt…</p>
          ) : null}
          {enrichment.status === "error" ? (
            <p className="citationStatus">Source excerpt is temporarily unavailable.</p>
          ) : null}
          {markdownContent ? (
            <div className="citationMarkdown">
              <ReactMarkdown components={dialogMarkdownComponents} remarkPlugins={[remarkGfm]}>
                {markdownContent}
              </ReactMarkdown>
            </div>
          ) : null}
          {enrichment.status === "missing" ? (
            <p className="citationStatus">Original source excerpt is unavailable; showing the stored summary.</p>
          ) : null}
          {enrichment.status === "stale" ? (
            <p className="citationStatus">Source content was reloaded, but the indexed chunk has changed since this reply.</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
