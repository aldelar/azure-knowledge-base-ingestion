import { render, screen } from "@testing-library/react";

import { CopilotMessageRenderer } from "../../components/CopilotMessageRenderer";

const AssistantMessage = ({ message }: any) => <div data-testid="assistant-message">{message?.content ?? ""}</div>;
const UserMessage = ({ message }: any) => <div data-testid="user-message">{message?.content ?? ""}</div>;

describe("CopilotMessageRenderer", () => {
  it("renders assistant tool calls with matched tool results inline", () => {
    const assistantMessage = {
      id: "assistant-1",
      role: "assistant",
      content: "I searched the knowledge base.",
      toolCalls: [
        {
          id: "tool-call-1",
          type: "function",
          function: {
            name: "search_knowledge_base",
            arguments: JSON.stringify({ query: "azure ai search" }),
          },
        },
      ],
    };

    const toolResultMessage = {
      id: "tool-result-1",
      role: "tool",
      toolCallId: "tool-call-1",
      content: JSON.stringify({
        results: [{ title: "Azure AI Search overview", section_header: "Overview" }],
      }),
    };

    render(
      <CopilotMessageRenderer
        AssistantMessage={AssistantMessage}
        UserMessage={UserMessage}
        inProgress={false}
        index={0}
        isCurrentMessage={false}
        message={assistantMessage as any}
        messages={[assistantMessage, toolResultMessage] as any}
      />,
    );

    expect(screen.getByTestId("assistant-message")).toHaveTextContent("I searched the knowledge base.");
    expect(screen.getByText("Knowledge Search")).toBeInTheDocument();
    expect(screen.getByText("azure ai search")).toBeInTheDocument();
    expect(screen.getByText("Azure AI Search overview")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("renumbers assistant references to match deduplicated citation cards", () => {
    const assistantMessage = {
      id: "assistant-refs",
      role: "assistant",
      content: "See Ref #7 and Ref #11 for details.",
      toolCalls: [
        {
          id: "tool-call-refs",
          type: "function",
          function: {
            name: "search_knowledge_base",
            arguments: JSON.stringify({ query: "architecture" }),
          },
        },
      ],
    };

    const toolResultMessage = {
      id: "tool-result-refs",
      role: "tool",
      toolCallId: "tool-call-refs",
      content: JSON.stringify({
        results: [
          { ref_number: 4, title: "Overview", section_header: "Intro", content: "Same content" },
          { ref_number: 7, title: "Overview", section_header: "Intro", content: "Same content" },
          { ref_number: 11, title: "Details", section_header: "Body", content: "Different content" },
        ],
      }),
    };

    render(
      <CopilotMessageRenderer
        AssistantMessage={AssistantMessage}
        UserMessage={UserMessage}
        inProgress={false}
        index={0}
        isCurrentMessage={false}
        message={assistantMessage as any}
        messages={[assistantMessage, toolResultMessage] as any}
      />,
    );

    expect(screen.getByTestId("assistant-message")).toHaveTextContent(
      "See [Ref #1](#citation-ref-1) and [Ref #2](#citation-ref-2) for details.",
    );
  });

  it("shows running tool activity before the tool result arrives", () => {
    const assistantMessage = {
      id: "assistant-2",
      role: "assistant",
      toolCalls: [
        {
          id: "tool-call-2",
          type: "function",
          function: {
            name: "search_knowledge_base",
            arguments: JSON.stringify({ query: "content understanding" }),
          },
        },
      ],
    };

    render(
      <CopilotMessageRenderer
        AssistantMessage={AssistantMessage}
        UserMessage={UserMessage}
        inProgress={true}
        index={0}
        isCurrentMessage={true}
        message={assistantMessage as any}
        messages={[assistantMessage] as any}
      />,
    );

    expect(screen.getByText("content understanding")).toBeInTheDocument();
    expect(screen.getByText("Searching")).toBeInTheDocument();
    expect(screen.getByText("The agent is collecting article matches and ranking the best sections.")).toBeInTheDocument();
  });

  it("does not render standalone tool result messages separately", () => {
    const toolResultMessage = {
      id: "tool-result-2",
      role: "tool",
      toolCallId: "tool-call-2",
      content: JSON.stringify({ results: [] }),
    };

    const { container } = render(
      <CopilotMessageRenderer
        AssistantMessage={AssistantMessage}
        UserMessage={UserMessage}
        inProgress={false}
        index={1}
        isCurrentMessage={true}
        message={toolResultMessage as any}
        messages={[toolResultMessage] as any}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders reasoning messages without dropping them from resumed threads", () => {
    render(
      <CopilotMessageRenderer
        AssistantMessage={AssistantMessage}
        UserMessage={UserMessage}
        inProgress={false}
        index={0}
        isCurrentMessage={false}
        message={{ id: "reasoning-1", role: "reasoning", content: "Comparing the best citation matches." } as any}
        messages={[] as any}
      />,
    );

    expect(screen.getByText("Reasoning")).toBeInTheDocument();
    expect(screen.getByText("Comparing the best citation matches.")).toBeInTheDocument();
  });
});