import { act, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BackToTop } from "./back-to-top";

describe("BackToTop", () => {
  it("removes the hidden control from the keyboard focus order", () => {
    Object.defineProperty(window, "scrollY", { configurable: true, value: 0 });
    const { container } = render(<BackToTop />);

    const button = container.querySelector("button");
    expect(button).toHaveAttribute("tabindex", "-1");
    expect(button).toHaveAttribute("aria-hidden", "true");
  });

  it("restores keyboard access after the page is scrolled", () => {
    Object.defineProperty(window, "scrollY", { configurable: true, value: 0, writable: true });
    const { container } = render(<BackToTop />);

    Object.defineProperty(window, "scrollY", { configurable: true, value: 500, writable: true });
    act(() => window.dispatchEvent(new Event("scroll")));

    const button = container.querySelector("button");
    expect(button).toHaveAttribute("tabindex", "0");
    expect(button).toHaveAttribute("aria-hidden", "false");
  });
});
