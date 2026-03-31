"use client";

import { coerceMessageContent } from "../lib/messageContent";
import {
  canonicalizeCitations,
  extractInlineCitationImages,
  getCitationImages,
  normalizeCitationRow,
} from "./chatMessageTransforms";

type SearchToolRendererProps = {
  status?: string;
  args?: {
    query?: unknown;
  } | null;
  result?: {
    results?: unknown[];
  } | null;
};

export function SearchToolRenderer({ status, args, result }: SearchToolRendererProps) {
  const rawRows = Array.isArray(result?.results) ? result.results.map((row) => normalizeCitationRow(row)) : [];
  const { citations: rows } = canonicalizeCitations(rawRows);
  const isWorking = status === "inProgress" || status === "executing" || status === "running";
  const query = coerceMessageContent(args?.query) ?? "Preparing search request";

  return (
    <section className="toolCard" data-status={status ?? "idle"}>
      <div className="toolCardHeader">
        <span className="toolCardEyebrow">Knowledge Search</span>
        <span className={`toolCardStatus${isWorking ? " working" : ""}`}>
          {isWorking ? "Searching" : "Completed"}
        </span>
      </div>
      <p className="toolCardQuery">{query}</p>
      {rows.length > 0 ? (
        <div className="citationDeck">
          {rows.map((row, index) => {
            const { content, images: inlineImages } = extractInlineCitationImages(row.content ?? "", row, rows);
            const citationImages = getCitationImages(row, rows).concat(
              inlineImages.filter((image) => !getCitationImages(row, rows).some((entry) => entry.url === image.url)),
            );
            const refLabel = row.ref_number ? `Ref #${row.ref_number}` : `Result ${index + 1}`;

            return (
              <article
                id={row.ref_number ? `citation-ref-${row.ref_number}` : undefined}
                className="citationCard"
                key={`${row.ref_number ?? index}-${row.title ?? "result"}`}
              >
                <div className="citationCardHeader">
                  <span className="citationBadge">{refLabel}</span>
                  <div>
                    <strong>{row.title ?? "Knowledge base result"}</strong>
                    <span>{row.section_header ?? "Relevant section"}</span>
                  </div>
                </div>
                {content ? <p className="citationPreview">{content}</p> : null}
                {citationImages.length > 0 ? (
                  <div className="citationImageStrip">
                    {citationImages.map((image, imageIndex) => (
                      <img
                        alt={image.alt || `${refLabel} image ${imageIndex + 1}`}
                        className="citationImage"
                        key={`${image.url}-${imageIndex}`}
                        loading="lazy"
                        src={image.url}
                      />
                    ))}
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