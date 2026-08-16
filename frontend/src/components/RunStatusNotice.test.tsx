import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RunStatusNotice } from "./RunStatusNotice";

describe("RunStatusNotice", () => {
  it("makes a free-tier quota pause visible", () => {
    render(
      <RunStatusNotice
        run={{
          id: "run-1",
          topic_id: "topic-1",
          draft_id: null,
          kind: "research",
          trigger: "manual",
          status: "paused_quota",
          progress_stage: "quota_exhausted",
          error_message: "Groq free-tier quota is currently exhausted",
          documents_processed: 0,
          model_requests: 1,
          created_at: "2026-08-16T00:00:00Z",
        }}
      />,
    );

    expect(screen.getByText("Research paused by the free-tier limit")).toBeVisible();
    expect(screen.getByText(/completed work was saved/i)).toBeVisible();
  });
});
