"use client";

import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";

import { SearchCitationResult } from "../lib/types";

export type RegisteredCitation = {
  citation: SearchCitationResult;
  threadId: string | null;
  toolCallId: string | undefined;
};

type CitationDialogState = {
  /** The ref number currently open in the dialog, or null if closed. */
  openRefNumber: number | null;
  /** Open the dialog for a given ref number. */
  openCitation: (refNumber: number) => void;
  /** Close the dialog. */
  closeCitation: () => void;
  /** Register a citation so the dialog can look it up by ref number. */
  registerCitation: (refNumber: number, entry: RegisteredCitation) => void;
  /** Look up a registered citation by ref number. */
  getCitation: (refNumber: number) => RegisteredCitation | undefined;
};

const CitationDialogContext = createContext<CitationDialogState | null>(null);

export function CitationDialogProvider({ children }: { children: ReactNode }) {
  const [openRefNumber, setOpenRefNumber] = useState<number | null>(null);
  const [registry, setRegistry] = useState<Map<number, RegisteredCitation>>(new Map());

  const registerCitation = useCallback((refNumber: number, entry: RegisteredCitation) => {
    setRegistry((current) => {
      const existing = current.get(refNumber);
      if (
        existing &&
        existing.citation === entry.citation &&
        existing.threadId === entry.threadId &&
        existing.toolCallId === entry.toolCallId
      ) {
        return current;
      }

      const next = new Map(current);
      next.set(refNumber, entry);
      return next;
    });
  }, []);

  const getCitation = useCallback(
    (refNumber: number) => registry.get(refNumber),
    [registry],
  );

  const openCitation = useCallback((refNumber: number) => {
    setOpenRefNumber(refNumber);
  }, []);

  const closeCitation = useCallback(() => {
    setOpenRefNumber(null);
  }, []);

  const value = useMemo<CitationDialogState>(
    () => ({ openRefNumber, openCitation, closeCitation, registerCitation, getCitation }),
    [openRefNumber, openCitation, closeCitation, registerCitation, getCitation],
  );

  return (
    <CitationDialogContext.Provider value={value}>
      {children}
    </CitationDialogContext.Provider>
  );
}

export function useCitationDialog(): CitationDialogState {
  const context = useContext(CitationDialogContext);
  if (!context) {
    throw new Error("useCitationDialog must be used within a CitationDialogProvider");
  }
  return context;
}

export function useCitationDialogOptional(): CitationDialogState | null {
  return useContext(CitationDialogContext);
}
