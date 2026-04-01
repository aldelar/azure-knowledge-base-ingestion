"use client";

import { useState } from "react";

import { ConversationRecord } from "../lib/types";

type ConversationSidebarProps = {
  activeThreadId: string | null;
  conversations: ConversationRecord[];
  onCreateConversation: () => Promise<void>;
  onDeleteConversation: (threadId: string) => Promise<void>;
  onRenameConversation: (threadId: string, title: string) => Promise<void>;
  onSelectConversation: (threadId: string) => void;
};

function TrashIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="16" viewBox="0 0 24 24" width="16">
      <path
        d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

export function ConversationSidebar({
  activeThreadId,
  conversations,
  onCreateConversation,
  onDeleteConversation,
  onRenameConversation,
  onSelectConversation,
}: ConversationSidebarProps) {
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [pendingDeleteThreadId, setPendingDeleteThreadId] = useState<string | null>(null);

  const pendingDeleteConversation =
    conversations.find((conversation) => conversation.id === pendingDeleteThreadId) ?? null;

  function startRename(conversation: ConversationRecord): void {
    setEditingThreadId(conversation.id);
    setDraftTitle(conversation.name);
  }

  function cancelRename(): void {
    setEditingThreadId(null);
    setDraftTitle("");
  }

  async function commitRename(threadId: string): Promise<void> {
    const currentConversation = conversations.find((conversation) => conversation.id === threadId);
    const nextTitle = draftTitle.trim();

    setEditingThreadId(null);
    setDraftTitle("");

    if (!currentConversation || !nextTitle || nextTitle === currentConversation.name) {
      return;
    }

    await onRenameConversation(threadId, nextTitle);
  }

  async function confirmDelete(): Promise<void> {
    if (!pendingDeleteConversation) {
      return;
    }

    setPendingDeleteThreadId(null);
    await onDeleteConversation(pendingDeleteConversation.id);
  }

  return (
    <>
      <aside className="conversationRail">
        <div className="conversationRailHeader">
          <p className="conversationRailLabel">Conversations</p>
          <button className="conversationCreateButton" onClick={() => void onCreateConversation()} type="button">
            New chat
          </button>
        </div>
        <div className="conversationList" role="list">
          {conversations.map((conversation) => {
            const isActive = conversation.id === activeThreadId;
            const isEditing = conversation.id === editingThreadId;

            return (
              <article className={`conversationItem${isActive ? " active" : ""}`} key={conversation.id} role="listitem">
                {isEditing ? (
                  <input
                    aria-label={`Rename ${conversation.name}`}
                    autoFocus
                    className="conversationTitleInput"
                    onBlur={() => void commitRename(conversation.id)}
                    onChange={(event) => setDraftTitle(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        void commitRename(conversation.id);
                      }

                      if (event.key === "Escape") {
                        event.preventDefault();
                        cancelRename();
                      }
                    }}
                    type="text"
                    value={draftTitle}
                  />
                ) : (
                  <button
                    aria-pressed={isActive}
                    className="conversationItemSelect"
                    onClick={() => onSelectConversation(conversation.id)}
                    type="button"
                  >
                    <span
                      className="conversationItemTitle"
                      onDoubleClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        startRename(conversation);
                      }}
                    >
                      {conversation.name}
                    </span>
                  </button>
                )}
                <div className="conversationItemMetaRow">
                  <small>{new Date(conversation.updatedAt).toLocaleString()}</small>
                  <button
                    aria-label={`Delete ${conversation.name}`}
                    className="conversationDeleteButton"
                    onClick={() => setPendingDeleteThreadId(conversation.id)}
                    type="button"
                  >
                    <TrashIcon />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
        <div className="conversationRailFooter">
          <p>Tool activity, search citations, and resumed turns stay attached to the selected thread.</p>
        </div>
      </aside>
      {pendingDeleteConversation ? (
        <div className="conversationDialogOverlay" onClick={() => setPendingDeleteThreadId(null)} role="presentation">
          <div
            aria-describedby="conversation-delete-description"
            aria-labelledby="conversation-delete-title"
            aria-modal="true"
            className="conversationDialog"
            onClick={(event) => event.stopPropagation()}
            role="alertdialog"
          >
            <p className="conversationDialogEyebrow">Delete conversation</p>
            <h2 id="conversation-delete-title">Remove “{pendingDeleteConversation.name}”?</h2>
            <p className="conversationDialogDescription" id="conversation-delete-description">
              This removes the conversation from the sidebar. Start a new chat if you want to keep working after it is gone.
            </p>
            <div className="conversationDialogActions">
              <button
                className="conversationDialogButton secondary"
                onClick={() => setPendingDeleteThreadId(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="conversationDialogButton danger"
                onClick={() => void confirmDelete()}
                type="button"
              >
                Delete conversation
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}