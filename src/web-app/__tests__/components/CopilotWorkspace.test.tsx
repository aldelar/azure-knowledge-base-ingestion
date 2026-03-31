import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CopilotWorkspace } from "../../components/CopilotWorkspace";

const copilotChatSpy = vi.fn();

vi.mock("@copilotkit/react-core", () => ({
  CopilotKit: ({ children }: { children: React.ReactNode }) => <div data-testid="copilot-kit">{children}</div>,
}));

vi.mock("@copilotkit/react-ui", () => ({
  CopilotChat: (props: any) => {
    copilotChatSpy(props);
    return <div data-testid="copilot-chat">{props.labels?.title}</div>;
  },
}));

vi.mock("../../components/ChatHistoryHydrator", () => ({
  ChatHistoryHydrator: () => <div data-testid="history-hydrator" />,
}));

vi.mock("../../components/CitationAwareAssistantMessage", () => ({
  CitationAwareAssistantMessage: () => <div data-testid="assistant-message" />,
}));

vi.mock("../../components/CopilotMessageRenderer", () => ({
  CopilotMessageRenderer: () => null,
}));

vi.mock("../../components/ConversationSidebar", () => ({
  ConversationSidebar: () => <aside data-testid="conversation-sidebar" />,
}));

describe("CopilotWorkspace", () => {
  beforeEach(() => {
    copilotChatSpy.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [{ id: "thread-1", name: "Azure AI chat", updatedAt: "2026-03-31T00:00:00Z" }],
      }),
    );
  });

  it("renders Azure AI branding without Contoso references", async () => {
    render(<CopilotWorkspace />);

    await waitFor(() => {
      expect(screen.getByText("Azure AI Knowledge")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Azure AI Knowledge Agent" })).toBeInTheDocument();
      expect(screen.getByText(/indexed Azure AI content/i)).toBeInTheDocument();
      expect(screen.queryByText("Contoso Robotics")).not.toBeInTheDocument();
      expect(copilotChatSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          labels: expect.objectContaining({
            title: "Azure AI chat",
            initial: ["Ask about Azure AI Search, Content Understanding, or other indexed Azure AI content."],
            placeholder: "Ask a question about Azure AI knowledge…",
          }),
        }),
      );
    });
  });
});