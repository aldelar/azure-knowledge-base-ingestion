import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReactNode } from "react";

import {
  CitationDialogProvider,
  useCitationDialog,
  useCitationDialogOptional,
} from "../../components/CitationDialogContext";

function wrapper({ children }: { children: ReactNode }) {
  return <CitationDialogProvider>{children}</CitationDialogProvider>;
}

describe("CitationDialogContext", () => {
  it("starts with no open citation", () => {
    const { result } = renderHook(() => useCitationDialog(), { wrapper });
    expect(result.current.openRefNumber).toBeNull();
  });

  it("opens and closes a citation by ref number", () => {
    const { result } = renderHook(() => useCitationDialog(), { wrapper });

    act(() => result.current.openCitation(3));
    expect(result.current.openRefNumber).toBe(3);

    act(() => result.current.closeCitation());
    expect(result.current.openRefNumber).toBeNull();
  });

  it("registers and retrieves a citation", () => {
    const { result } = renderHook(() => useCitationDialog(), { wrapper });
    const entry = {
      citation: { ref_number: 1, title: "Test" },
      threadId: "thread-1",
      toolCallId: "tool-1",
    };

    act(() => result.current.registerCitation(1, entry));
    expect(result.current.getCitation(1)).toEqual(entry);
    expect(result.current.getCitation(2)).toBeUndefined();
  });

  it("returns null from useCitationDialogOptional when outside provider", () => {
    const { result } = renderHook(() => useCitationDialogOptional());
    expect(result.current).toBeNull();
  });

  it("throws from useCitationDialog when outside provider", () => {
    expect(() => {
      renderHook(() => useCitationDialog());
    }).toThrow("useCitationDialog must be used within a CitationDialogProvider");
  });
});
