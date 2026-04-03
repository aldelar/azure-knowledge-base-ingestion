import {
  canonicalizeCitations,
  extractInlineCitationImages,
  linkCitationMarkers,
  transformAssistantContent,
} from "../../components/chatMessageTransforms";

describe("linkCitationMarkers", () => {
  it("rewrites ref markers into local citation anchors", () => {
    expect(linkCitationMarkers("See [Ref #2] and [Ref #11] for details.")).toBe(
      "See [Ref #2](#citation-ref-2) and [Ref #11](#citation-ref-11) for details.",
    );
  });

  it("does not rewrite markers that are already links", () => {
    expect(linkCitationMarkers("See [Ref #3](#citation-ref-3)."))
      .toBe("See [Ref #3](#citation-ref-3).");
  });

  it("links bare ref mentions after they are normalized", () => {
    expect(linkCitationMarkers("See Ref #4 and Ref #9 for details."))
      .toBe("See [Ref #4](#citation-ref-4) and [Ref #9](#citation-ref-9) for details.");
  });
});

describe("canonicalizeCitations", () => {
  it("deduplicates rows deterministically and renumbers refs", () => {
    const { citations, refNumberMap } = canonicalizeCitations([
      { ref_number: 4, title: "Overview", section_header: "Intro", content: "Same content" },
      { ref_number: 7, title: "Overview", section_header: "Intro", content: "Same content" },
      { ref_number: 11, title: "Details", section_header: "Body", content: "Different content" },
    ]);

    expect(citations).toHaveLength(2);
    expect(citations.map((citation) => citation.ref_number)).toEqual([1, 2]);
    expect(refNumberMap.get(4)).toBe(1);
    expect(refNumberMap.get(7)).toBe(1);
    expect(refNumberMap.get(11)).toBe(2);
  });
});

describe("transformAssistantContent", () => {
  it("renumbers refs and links them but does not insert refs the LLM omitted", () => {
    const content = "See ref#7 for the overview.";
    const transformed = transformAssistantContent(content, [
      { ref_number: 4, title: "Overview", section_header: "Intro", content: "Same content" },
      { ref_number: 7, title: "Overview", section_header: "Intro", content: "Same content" },
      { ref_number: 11, title: "Details", section_header: "Body", content: "Different content" },
    ]);

    expect(transformed).toContain("See [Ref #1](#citation-ref-1) for the overview.");
    expect(transformed).not.toContain("Ref #2");
    expect(transformed).not.toContain("Sources:");
  });

  it("normalizes malformed image urls and indexed image refs", () => {
    const transformed = transformAssistantContent(
      "Diagram: ![arch](attachment:arch.png) and [Image: architecture](images/arch.png)",
      [
        {
          ref_number: 2,
          article_id: "contoso-article",
          title: "Architecture",
          section_header: "Images",
          content: "",
          image_urls: ["images/arch.png"],
        },
      ],
    );

    expect(transformed).toContain("![arch](/api/images/contoso-article/images/arch.png)");
    expect(transformed).toContain("![architecture](/api/images/contoso-article/images/arch.png)");
  });

  it("does not inject fallback images the LLM did not embed", () => {
    const transformed = transformAssistantContent(
      "See [Ref #3] for the diagram.",
      [
        {
          ref_number: 3,
          article_id: "contoso-article",
          title: "Architecture",
          section_header: "Images",
          content: "",
          image_urls: ["images/arch.png"],
        },
      ],
    );

    expect(transformed).toContain("See [Ref #1](#citation-ref-1) for the diagram.");
    expect(transformed).not.toContain("![Ref #1 image]");
    expect(transformed).not.toContain("Sources:");
  });

  it("does not insert missing refs the LLM did not mention", () => {
    const transformed = transformAssistantContent(
      "## Agentic Retrieval Workflow\n\nAgentic retrieval improves recall for complex questions.",
      [
        {
          ref_number: 9,
          title: "Agentic retrieval in Azure AI Search",
          section_header: "Overview",
          content: "Agentic retrieval improves recall for complex questions.",
        },
      ],
    );

    expect(transformed).not.toContain("Ref #1");
    expect(transformed).toContain("Agentic retrieval improves recall for complex questions.");
  });
});

describe("extractInlineCitationImages", () => {
  it("rewrites indexed image refs into proxy backed inline images before extraction", () => {
    const result = extractInlineCitationImages(
      "Reference body. [Image: architecture](images/arch.png)",
      {
        ref_number: 1,
        article_id: "contoso-article",
        content: "Reference body. [Image: architecture](images/arch.png)",
      },
      [
        {
          ref_number: 1,
          article_id: "contoso-article",
          content: "Reference body. [Image: architecture](images/arch.png)",
          image_urls: ["images/arch.png"],
        },
      ],
    );

    expect(result.content).toBe("Reference body.");
    expect(result.images).toEqual([
      {
        alt: "architecture",
        url: "/api/images/contoso-article/images/arch.png",
      },
    ]);
  });
});