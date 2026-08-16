import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCountUp } from "./use-count-up";

describe("useCountUp", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("reads the reduced-motion preference and skips count animation", () => {
    const matchMedia = vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    Object.defineProperty(window, "matchMedia", { configurable: true, value: matchMedia });
    const requestAnimationFrame = vi.spyOn(window, "requestAnimationFrame");

    const { result } = renderHook(() => useCountUp(42));

    expect(matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)");
    expect(result.current).toBe(42);
    expect(requestAnimationFrame).not.toHaveBeenCalled();
  });
});
