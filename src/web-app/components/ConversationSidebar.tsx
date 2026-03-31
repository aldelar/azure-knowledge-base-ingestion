"use client";

import { ConversationRecord } from "../lib/types";

type ConversationSidebarProps = {
  activeThreadId: string | null;
  conversations: ConversationRecord[];
  onCreateConversation: () => Promise<void>;
  onDeleteConversation: (threadId: string) => Promise<void>;
  onRenameConversation: (threadId: string) => Promise<void>;
  onSelectConversation: (threadId: string) => void;
};

export function ConversationSidebar({
  activeThreadId,
  conversations,
  onCreateConversation,
  onDeleteConversation,
  onRenameConversation,
  onSelectConversation,
}: ConversationSidebarProps) {
  return (
    <aside className="conversationRail">
      <div className="conversationRailHeader">
        <div>
          <p className="conversationRailLabel">Threads</p>
          <h2 className="conversationRailTitle">Conversation history</h2>
        </div>
        <button className="conversationCreateButton" onClick={() => void onCreateConversation()} type="button">
          New chat
        </button>
      </div>
      <div className="conversationRailIntro">
        <strong>{conversations.length}</strong>
        <span>{conversations.length === 1 ? "Saved thread" : "Saved threads"} with restorable AG-UI history.</span>
      </div>
      <div className="conversationList" role="list">
        {conversations.map((conversation) => (
          <article
            className={`conversationItem${conversation.id === activeThreadId ? " active" : ""}`}
            key={conversation.id}
            role="listitem"
          >
            <button
              aria-pressed={conversation.id === activeThreadId}
              className="conversationItemSelect"
              onClick={() => onSelectConversation(conversation.id)}
              type="button"
            >
              <span className="conversationItemTitle">{conversation.name}</span>
              <span className="conversationItemMeta">
                <small>{new Date(conversation.updatedAt).toLocaleString()}</small>
                {conversation.id === activeThreadId ? <em>Active</em> : null}
              </span>
            </button>
            <div className="conversationItemActions">
              <button
                className="conversationItemAction"
                onClick={() => void onRenameConversation(conversation.id)}
                type="button"
              >
                Rename
              </button>
              <button
                className="conversationItemAction danger"
                onClick={() => void onDeleteConversation(conversation.id)}
                type="button"
              >
                Delete
              </button>
            </div>
          </article>
        ))}
      </div>
      <div className="conversationRailFooter">
        <p>Tool activity, search citations, and resumed turns stay attached to the selected thread.</p>
      </div>
    </aside>
  );
}