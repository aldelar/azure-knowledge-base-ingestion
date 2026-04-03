import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";

import { ConversationThreadProvider } from "../../components/ConversationThreadContext";
import { SearchToolRenderer } from "../../components/SearchToolRenderer";

describe("SearchToolRenderer", () => {
  it("renders the query and top results", () => {
    render(
      <SearchToolRenderer
        args={{ query: "azure ai search" }}
        result={{
          results: [
            { title: "Azure AI Search overview", section_header: "What it does" },
            { title: "Search security", section_header: "Network isolation" },
          ],
        }}
        status="complete"
      />,
    );

    expect(screen.getByText("azure ai search")).toBeInTheDocument();
    expect(screen.getByText("Azure AI Search overview")).toHaveClass("citationCardTitle");
    expect(screen.getByText("What it does")).toHaveClass("citationCardPreview");
    expect(screen.getByText("Network isolation")).toHaveClass("citationCardPreview");
  });

  it("renders collapsed citation markdown with links and proxy-backed images", async () => {
    const user = userEvent.setup();

    render(
      <SearchToolRenderer
        args={{ query: { type: "text", value: "content understanding" } }}
        result={{
          results: [
            {
              ref_number: 7,
              title: { type: "text", value: "Content Understanding overview" },
              section_header: { type: "text", value: "Image grounding" },
              content: [
                {
                  type: "text",
                  value: "The service returns grounded [documentation](https://learn.microsoft.com/azure/search/).",
                },
                { type: "text", value: "![Grounding diagram](/api/images/contoso/diagram.png)" },
              ],
            },
          ],
        }}
        status="complete"
      />,
    );

    expect(screen.getByText("Ref #1")).toBeInTheDocument();
    expect(screen.getByText("Content Understanding overview")).toHaveClass("citationCardTitle");
    expect(screen.getByText("The service returns grounded documentation.")).toHaveClass("citationCardPreview");
    expect(screen.queryByText("Expand")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "documentation" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Ref #1/i }));

    expect(screen.getByRole("link", { name: "documentation" })).toHaveAttribute(
      "href",
      "https://learn.microsoft.com/azure/search/",
    );
    expect(screen.getByRole("img", { name: "Grounding diagram" })).toHaveAttribute(
      "src",
      "/api/images/contoso/diagram.png",
    );
    expect(screen.getByRole("img", { name: "Grounding diagram" })).toHaveClass(
      "citationImage",
      "citationMarkdownImage",
    );
  });

  it("renders markdown tables with the citation table wrapper", async () => {
    const user = userEvent.setup();

    render(
      <SearchToolRenderer
        args={{ query: "agentic pricing" }}
        result={{
          results: [
            {
              ref_number: 1,
              title: "Agentic retrieval pricing",
              section_header: "Pricing table",
              content: "| Plan | Description |\n| --- | --- |\n| Free | 50 million free agentic reasoning tokens per month. |\n| Standard | Pay-as-you-go after the free quota is used. |",
            },
          ],
        }}
        status="complete"
      />,
    );

    await user.click(screen.getByRole("button", { name: /Ref #1/i }));

    const table = screen.getByRole("table");

    expect(table).toHaveClass("citationTable");
    expect(table.parentElement).toHaveClass("citationTableWrapper");
    expect(screen.getByText("Plan")).toBeInTheDocument();
    expect(screen.getByText("50 million free agentic reasoning tokens per month.")).toBeInTheDocument();
  });

  it("rewrites indexed image refs and relative image urls into proxy-backed images", async () => {
    const user = userEvent.setup();

    render(
      <SearchToolRenderer
        args={{ query: "architecture" }}
        result={{
          results: [
            {
              ref_number: 2,
              article_id: "contoso-article",
              title: "Architecture guide",
              section_header: "Diagrams",
              content: "See the overview. [Image: architecture](images/arch.png)",
              image_urls: ["images/arch.png"],
            },
          ],
        }}
        status="complete"
      />,
    );

    await user.click(screen.getByRole("button", { name: /Ref #1/i }));

    expect(screen.getByText("See the overview.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "architecture" })).toHaveAttribute(
      "src",
      "/api/images/contoso-article/images/arch.png",
    );
  });

  it("renders structured tool payloads without passing objects to React", async () => {
    const user = userEvent.setup();

    render(
      <SearchToolRenderer
        args={{ query: [{ type: "text", value: "agentic retrieval" }] }}
        result={{
          results: [
            {
              ref_number: "8",
              title: [{ type: "text", value: "Agentic retrieval" }],
              section_header: { type: "text", value: "Execution flow" },
              content: { type: "text", value: "The agent can plan and refine its search steps." },
              images: [
                {
                  url: { type: "text", value: "/api/images/contoso/agentic-flow.png" },
                  alt: { type: "text", value: "Agentic flow" },
                },
              ],
            },
          ],
        }}
        status="complete"
      />,
    );

    expect(screen.getByText("agentic retrieval")).toBeInTheDocument();
    expect(screen.getByText("Agentic retrieval")).toBeInTheDocument();
    expect(screen.getByText("The agent can plan and refine its search steps.")).toHaveClass("citationCardPreview");

    await user.click(screen.getByRole("button", { name: /Ref #1/i }));

    expect(screen.getAllByText("The agent can plan and refine its search steps.")).toHaveLength(2);
    expect(screen.getByRole("img", { name: "Agentic flow" })).toHaveAttribute(
      "src",
      "/api/images/contoso/agentic-flow.png",
    );
  });

  it("loads full source excerpts automatically when compact stored citations are expanded", async () => {
    const user = userEvent.setup();
    let resolveResponse: ((response: Response) => void) | null = null;
    const fetchMock = vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveResponse = resolve;
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ConversationThreadProvider threadId="thread-123">
        <SearchToolRenderer
          args={{ query: "architecture" }}
          result={{
            results: [
              {
                ref_number: 1,
                chunk_id: "article-1_0",
                title: "Architecture guide",
                section_header: "Diagrams",
                summary: "Stored compact summary.",
                content_source: "summary",
              },
            ],
          }}
          status="complete"
          toolCallId="tool-call-1"
        />
      </ConversationThreadProvider>,
    );

    expect(screen.getByText("Stored compact summary.")).toHaveClass("citationCardPreview");

    await user.click(screen.getByRole("button", { name: /Ref #1/i }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/thread-123/citations/tool-call-1/1",
      { cache: "no-store" },
    );
    expect(screen.queryByRole("button", { name: "Load source excerpt" })).not.toBeInTheDocument();
    expect(screen.getByText("Loading source excerpt…")).toBeInTheDocument();
    expect(screen.queryAllByText("Stored compact summary.")).toHaveLength(1);

    resolveResponse?.(
      new Response(
        JSON.stringify({
          status: "ready",
          citation: {
            ref_number: 1,
            chunk_id: "article-1_0",
            content: "Full chunk content loaded on demand.",
            content_source: "full",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    expect(await screen.findAllByText("Full chunk content loaded on demand.")).toHaveLength(2);
  });

  it("falls back to a readable summary when the source chunk no longer exists", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "missing" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ConversationThreadProvider threadId="thread-123">
        <SearchToolRenderer
          args={{ query: "content understanding" }}
          result={{
            results: [
              {
                ref_number: 2,
                chunk_id: "article-2_0",
                title: "Content Understanding overview",
                section_header: "Why use it",
                summary: "## Why use Content Understanding?\n\nSupporting details stay readable.",
                content_source: "summary",
              },
            ],
          }}
          status="complete"
          toolCallId="tool-call-1"
        />
      </ConversationThreadProvider>,
    );

    await user.click(screen.getByRole("button", { name: /Ref #1/i }));

    expect(await screen.findByText("Original source excerpt is unavailable; showing the stored summary.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/thread-123/citations/tool-call-1/1",
      { cache: "no-store" },
    );
    expect(screen.queryByRole("button", { name: "Load source excerpt" })).not.toBeInTheDocument();
    expect(screen.getAllByText("Why use Content Understanding?")).toHaveLength(2);
    expect(screen.queryByRole("heading", { name: "Why use Content Understanding?" })).not.toBeInTheDocument();
    expect(screen.getByText("Supporting details stay readable.")).toBeInTheDocument();
  });
});