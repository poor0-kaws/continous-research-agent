import { Hourglass, ShieldAlert } from "lucide-react";
import type { ResearchRun } from "../types";

interface Props {
  run?: ResearchRun;
}

export function RunStatusNotice({ run }: Props) {
  if (run?.status === "paused_quota") {
    return (
      <div className="run-notice run-notice--quota" role="status">
        <Hourglass size={17} />
        <span>
          <strong>Research paused by the free-tier limit</strong>
          Completed work was saved. Wait at least one minute before trying again.
        </span>
      </div>
    );
  }

  if (run?.status === "failed") {
    return (
      <div className="run-notice run-notice--error" role="alert">
        <ShieldAlert size={17} />
        <span>
          <strong>Research stopped safely</strong>
          {run.error_message}
        </span>
      </div>
    );
  }

  return null;
}
