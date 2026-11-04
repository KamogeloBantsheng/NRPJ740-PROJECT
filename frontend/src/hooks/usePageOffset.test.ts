import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { usePageOffset } from "./usePageOffset";

describe("usePageOffset", () => {
  it("keeps the position while the filters stay the same", () => {
    const { result } = renderHook(() => usePageOffset("a"));
    act(() => result.current[1](50));
    expect(result.current[0]).toBe(50);
  });

  it("returns to the first page when the filters change", () => {
    const { result, rerender } = renderHook(({ key }) => usePageOffset(key), { initialProps: { key: "a" } });
    act(() => result.current[1](50));
    rerender({ key: "b" });
    expect(result.current[0]).toBe(0);
  });
});
