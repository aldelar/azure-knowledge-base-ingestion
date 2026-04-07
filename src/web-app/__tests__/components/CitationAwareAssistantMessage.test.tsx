import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CitationAwareAssistantMessage } from "../../components/CitationAwareAssistantMessage";

const assistantMessageSpy = vi.fn();

vi.mock("@copilotkit/react-ui", () => ({
  AssistantMessage: (props: any) => {
    assistantMessageSpy(props);
    return <div data-testid="assistant-message">{props.message?.content ?? ""}</div>;
  },
}));

describe("CitationAwareAssistantMessage", () => {
  beforeEach(() => {
    assistantMessageSpy.mockReset();
  });

  it("normalizes structured content before passing it to CopilotKit", () => {
    render(
      <CitationAwareAssistantMessage
        message={{
          id: "assistant-1",
          role: "assistant",
          content: { type: "text", value: "See [Ref #2] for details." },
        } as any}
      />,
    );

    expect(screen.getByTestId("assistant-message")).toHaveTextContent(
      "See [Ref #2](#citation-ref-2) for details.",
    );
    expect(assistantMessageSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.objectContaining({
          content: "See [Ref #2](#citation-ref-2) for details.",
        }),
      }),
    );
  });

  it("passes markdownTagRenderers with custom a renderer to CopilotKit", () => {
    render(
      <CitationAwareAssistantMessage
        message={{
          id: "assistant-2",
          role: "assistant",
          content: "Check Ref #1 for details.",
        } as any}
      />,
    );

    const passedProps = assistantMessageSpy.mock.calls[0][0];
    expect(passedProps.markdownTagRenderers).toBeDefined();
    expect(typeof passedProps.markdownTagRenderers.a).toBe("function");
  });
});