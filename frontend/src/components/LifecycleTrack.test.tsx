import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LifecycleTrack } from "./LifecycleTrack";

afterEach(cleanup);

describe("LifecycleTrack", () => {
  it("marks earlier steps done and the current step", () => {
    render(<LifecycleTrack status="IN_PROGRESS" />);
    expect(screen.getByText("Assigned").className).toContain("is-done");
    expect(screen.getByText("In progress").className).toContain("is-current");
    expect(screen.getByText("Closed").className).not.toContain("is-done");
  });

  it("shows a rejected request stopped, not progressing", () => {
    render(<LifecycleTrack status="REJECTED" />);
    expect(screen.getByText("Rejected").className).toContain("is-stopped");
    expect(screen.queryByText("Approved")).toBeNull();
  });

  it("shows a closed request with every earlier step done", () => {
    render(<LifecycleTrack status="VERIFIED_CLOSED" />);
    expect(screen.getByText("Reported").className).toContain("is-done");
    expect(screen.getByText("Closed").getAttribute("aria-current")).toBe("step");
  });
});
