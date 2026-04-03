"use client";

import { startTransition, useState } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useConversationThreadId } from "./ConversationThreadContext";
import { SearchCitationEnrichmentResponse, SearchCitationResult } from "../lib/types";
import { coerceMessageContent } from "../lib/messageContent";
import {
  canonicalizeCitations,
  getCitationMarkdownContent,
  normalizeCitationRow,
} from "./chatMessageTransforms";

type SearchToolRendererProps = {
  status?: string;
  toolCallId?: string;
  args?: {
    query?: unknown;
  } | null;
  result?: {
    results?: unknown[];
  } | null;
};

type EnrichmentState = {
  citation?: SearchCitationResult;
  status: "idle" | "loading" | "ready" | "stale" | "missing" | "error";
};

type CitationBodyMode = "full" | "summary" | "loading" | "error";

function getCitationPreviewLine(markdownContent: string, fallback?: string): string {
  const previewLine = markdownContent
    .split("\n")
    .map((line) =>
      line
        .replace(/!\[([^\]]*)\]\([^\)]+\)/g, (_match, alt) => alt || "Image")
        .replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1")
        .replace(/^#{1,6}\s+/u, "")
        .replace(/^>\s+/u, "")
        .replace(/^[-*+]\s+/u, "")
        .replace(/^\d+\.\s+/u, "")
        .replace(/[*_`~]/g, "")
        .trim(),
    )
    .find((line) => line.length > 0);

  return previewLine ?? fallback ?? "Reference available";
}

function getCollapsedCitationLine(title: string | undefined, previewLine: string): {
  titleText: string;
  previewText: string | null;
} {
  const titleText = title?.trim() || "Knowledge base result";
  const normalizedPreview = previewLine.trim();

  if (!normalizedPreview || normalizedPreview === titleText || normalizedPreview.startsWith(titleText)) {
    return {
      titleText: normalizedPreview || titleText,
      previewText: null,
    };
  }

  return {
    titleText,
    previewText: normalizedPreview,
  };
}

function shouldAutoLoadCitation(canEnrich: boolean, enrichmentStatus?: EnrichmentState["status"]): boolean {
  if (!canEnrich) {
    return false;
  }

  return enrichmentStatus === undefined || enrichmentStatus === "idle" || enrichmentStatus === "error";
}

function getCitationBodyMode(
  canEnrich: boolean,
  enrichmentStatus: EnrichmentState["status"] | undefined,
  contentSource: SearchCitationResult["content_source"],
): CitationBodyMode {
  if (canEnrich) {
    if (enrichmentStatus === "ready" || enrichmentStatus === "stale") {
      return "full";
    }
    if (enrichmentStatus === "missing") {
      return "summary";
    }
    if (enrichmentStatus === "error") {
      return "error";
    }

    return "loading";
  }

  return contentSource === "summary" ? "summary" : "full";
}

function mergeCitation(base: SearchCitationResult, override?: SearchCitationResult): SearchCitationResult {
  return override ? { ...base, ...override } : base;
}

const citationMarkdownComponents: Components = {
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
      <table
        {...props}
        className={className ? `citationTable ${className}` : "citationTable"}
      >
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

const renderSummaryHeading: NonNullable<Components["h1"]> = ({ node, className, children, ...props }) => (
  <p
    {...props}
    className={className ? `citationSummaryHeading ${className}` : "citationSummaryHeading"}
  >
    {children}
  </p>
);

const citationSummaryMarkdownComponents: Components = {
  ...citationMarkdownComponents,
  h1: renderSummaryHeading,
  h2: renderSummaryHeading,
  h3: renderSummaryHeading,
  h4: renderSummaryHeading,
  h5: renderSummaryHeading,
  h6: renderSummaryHeading,
};

export function SearchToolRenderer({ status, toolCallId, args, result }: SearchToolRendererProps) {
  const threadId = useConversationThreadId();
  const [enrichments, setEnrichments] = useState<Record<string, EnrichmentState>>({});
  const [expandedRefs, setExpandedRefs] = useState<Record<string, boolean>>({});
  const rawRows = Array.isArray(result?.results) ? result.results.map((row) => normalizeCitationRow(row)) : [];
  const { citations: rows } = canonicalizeCitations(rawRows);
  const isWorking = status === "inProgress" || status === "executing" || status === "running";
  const query = coerceMessageContent(args?.query) ?? "Preparing search request";
  const displayRows = rows.map((row, index) => {
    const key = String(row.ref_number ?? index + 1);
    return mergeCitation(row, enrichments[key]?.citation);
  });

  async function loadCitation(refNumber: number): Promise<void> {
    if (!threadId || !toolCallId) {
      return;
    }

    const key = String(refNumber);
    setEnrichments((current) => ({
      ...current,
      [key]: { ...current[key], status: "loading" },
    }));

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
        setEnrichments((current) => ({
          ...current,
          [key]: {
            citation: payload.citation,
            status: payload.status === "ready" || payload.status === "stale" ? payload.status : "missing",
          },
        }));
      });
    } catch {
      startTransition(() => {
        setEnrichments((current) => ({
          ...current,
          [key]: { ...current[key], status: "error" },
        }));
      });
    }
  }

  return (
    <section className="toolCard" data-status={status ?? "idle"}>
      <div className="toolCardHeader">
        <span className="toolCardEyebrow">Knowledge Search</span>
        <span className={`toolCardStatus${isWorking ? " working" : ""}`}>
          {isWorking ? "Searching" : "Completed"}
        </span>
      </div>
      <p className="toolCardQuery">{query}</p>
      {displayRows.length > 0 ? (
        <div className="citationDeck">
          {displayRows.map((row, index) => {
            const key = String(row.ref_number ?? index + 1);
            const enrichment = enrichments[key];
            const canEnrich = Boolean(
              !isWorking
              && threadId
              && toolCallId
              && row.ref_number
              && row.chunk_id
              && row.content_source !== "full",
            );
            const markdownContent = getCitationMarkdownContent(row.content ?? row.summary ?? "", row, displayRows);
            const summaryMarkdownContent = getCitationMarkdownContent(row.summary ?? row.content ?? "", row, displayRows);
            const previewLine = getCitationPreviewLine(markdownContent, row.section_header);
            const refLabel = row.ref_number ? `Ref #${row.ref_number}` : `Result ${index + 1}`;
            const isExpanded = Boolean(expandedRefs[key]);
            const { titleText, previewText } = getCollapsedCitationLine(row.title, previewLine);
            const bodyMode = getCitationBodyMode(canEnrich, enrichment?.status, row.content_source);
            const bodyMarkdownContent = bodyMode === "summary" ? summaryMarkdownContent : markdownContent;
            const markdownComponents = bodyMode === "summary"
              ? citationSummaryMarkdownComponents
              : citationMarkdownComponents;
            const shouldRenderBodyMarkdown = bodyMode === "full" || bodyMode === "summary";

            return (
              <article
                id={row.ref_number ? `citation-ref-${row.ref_number}` : undefined}
                className="citationCard"
                key={`${row.ref_number ?? index}-${row.title ?? "result"}`}
              >
                <button
                  aria-controls={`citation-body-${key}`}
                  aria-expanded={isExpanded}
                  className="citationCardToggle"
                  onClick={() => {
                    const nextExpanded = !isExpanded;

                    if (nextExpanded && shouldAutoLoadCitation(canEnrich, enrichment?.status)) {
                      void loadCitation(row.ref_number as number);
                    }

                    setExpandedRefs((current) => ({
                      ...current,
                      [key]: nextExpanded,
                    }));
                  }}
                  type="button"
                >
                  <div className="citationCardHeader">
                    <span className="citationBadge">{refLabel}</span>
                    <div className="citationCardLine">
                      <strong className="citationCardTitle">{titleText}</strong>
                      {previewText ? <span className="citationCardSeparator">|</span> : null}
                      {previewText ? <span className="citationCardPreview">{previewText}</span> : null}
                    </div>
                  </div>
                </button>
                {isExpanded ? (
                  <div className="citationCardBody" id={`citation-body-${key}`}>
                    {bodyMode === "loading" ? (
                      <p className="citationStatus" role="status">Loading source excerpt…</p>
                    ) : null}
                    {bodyMode === "error" ? (
                      <p className="citationStatus">Source excerpt is temporarily unavailable.</p>
                    ) : null}
                    {shouldRenderBodyMarkdown && bodyMarkdownContent ? (
                      <div className={bodyMode === "summary" ? "citationMarkdown citationMarkdownSummary" : "citationMarkdown"}>
                        <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
                          {bodyMarkdownContent}
                        </ReactMarkdown>
                      </div>
                    ) : null}
                    {canEnrich && enrichment?.status === "missing" ? (
                      <p className="citationStatus">Original source excerpt is unavailable; showing the stored summary.</p>
                    ) : null}
                    {enrichment?.status === "stale" ? (
                      <p className="citationStatus">Source content was reloaded, but the indexed chunk has changed since this reply.</p>
                    ) : null}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : (
        <p className="toolCardHint">The agent is collecting article matches and ranking the best sections.</p>
      )}
    </section>
  );
}