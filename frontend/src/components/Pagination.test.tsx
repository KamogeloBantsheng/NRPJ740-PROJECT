import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Pagination } from "./Pagination";

afterEach(cleanup);

describe("Pagination", () => {
  it("is hidden when everything fits on one page", () => {
    const { container } = render(<Pagination total={50} limit={50} offset={0} onChange={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("moves forward by one page", () => {
    const onChange = vi.fn();
    render(<Pagination total={120} limit={50} offset={50} onChange={onChange} />);
    expect(screen.getByText("Page 2 of 3")).toBeTruthy();
    fireEvent.click(screen.getByText("Next Page"));
    expect(onChange).toHaveBeenCalledWith(100);
  });

  it("cannot move past the first or last page", () => {
    render(<Pagination total={60} limit={50} offset={0} onChange={() => {}} />);
    expect(screen.getByText<HTMLButtonElement>("Previous Page").disabled).toBe(true);
    cleanup();
    render(<Pagination total={60} limit={50} offset={50} onChange={() => {}} />);
    expect(screen.getByText<HTMLButtonElement>("Next Page").disabled).toBe(true);
  });
});
