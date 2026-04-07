import { render, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ChatHistoryHydrator } from "../../components/ChatHistoryHydrator";

const setMessages = vi.fn();

vi.mock("@copilotkit/react-core", () => ({
  useCopilotChatInternal: () => ({
    setMessages,
  }),
}));

describe("ChatHistoryHydrator", () => {
  beforeEach(() => {
    setMessages.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          messages: [
            {
              id: "assistant-1",
              role: "assistant",
              content: "Restored history",
              toolCalls: [
                {
                  id: "tool-call-1",
                  type: "function",
                  function: {
                    name: "search_knowledge_base",
                    arguments: '{"query":"azure ai search"}',
                  },
                },
              ],
            },
            {
              id: "reasoning-1",
              role: "reasoning",
              content: "Gathering the most relevant sections.",
            },
            {
              id: "tool-1",
              role: "tool",
              toolCallId: "tool-call-1",
              toolName: "search_knowledge_base",
              content: '{"results":[]}',
            },
          ],
        }),
      }),
    );
  });

  it("loads thread history into CopilotKit message state", async () => {
    render(<ChatHistoryHydrator threadId="thread-123" />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/api/conversations/thread-123/messages", {
        cache: "no-store",
      });
      expect(setMessages).toHaveBeenCalledWith([
        {
          id: "assistant-1",
          role: "assistant",
          content: "Restored history",
          toolCalls: [
            {
              id: "tool-call-1",
              type: "function",
              function: {
                name: "search_knowledge_base",
                arguments: '{"query":"azure ai search"}',
              },
            },
          ],
        },
        {
          id: "reasoning-1",
          role: "reasoning",
          content: "Gathering the most relevant sections.",
        },
        {
          id: "tool-1",
          role: "tool",
          toolCallId: "tool-call-1",
          toolName: "search_knowledge_base",
          content: '{"results":[]}',
        },
      ]);
    });
  });

  it("clears the visible history when the API response fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
      }),
    );

    render(<ChatHistoryHydrator threadId="thread-404" />);

    await waitFor(() => {
      expect(setMessages).toHaveBeenCalledWith([]);
    });
  });
});