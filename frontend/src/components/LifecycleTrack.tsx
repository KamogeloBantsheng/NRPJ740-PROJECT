/**
 * Where a request is on its route from report to closure (Table 5.1).
 */

import type { RequestStatus } from "../types/workflow";

const STEPS = ["Reported", "Approved", "Assigned", "In progress", "Completed", "Closed"];

// The position of each status on the track. Rework and questions stay on the step they belong to.
const POSITION: Record<RequestStatus, number> = {
  SUBMITTED: 0,
  NEEDS_CLARIFICATION: 0,
  REJECTED: 1,
  APPROVED: 1,
  ASSIGNED: 2,
  REOPENED: 3,
  IN_PROGRESS: 3,
  WORK_COMPLETED: 4,
  VERIFIED_CLOSED: 5,
};

// A status that replaces the usual step name while the request is in it
const STEP_LABEL: Partial<Record<RequestStatus, string>> = {
  NEEDS_CLARIFICATION: "Waiting for answer",
  REJECTED: "Rejected",
  REOPENED: "Reopened",
};

export function LifecycleTrack({ status }: { status: RequestStatus }) {
  const position = POSITION[status];

  return (
    <ol className="lifecycle-track" aria-label="Request progress">
      {STEPS.map((step, index) => {
        const isCurrent = index === position;
        const stateClass = isCurrent
          ? status === "REJECTED" || status === "REOPENED"
            ? "is-stopped"
            : "is-current"
          : index < position
            ? "is-done"
            : "";

        return (
          <li key={step} className={`lifecycle-step ${stateClass}`} aria-current={isCurrent ? "step" : undefined}>
            {(isCurrent && STEP_LABEL[status]) || step}
          </li>
        );
      })}
    </ol>
  );
}
