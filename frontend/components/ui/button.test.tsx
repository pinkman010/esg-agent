import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("applies only the requested size classes", () => {
    render(<Button size="sm">继续</Button>);

    const button = screen.getByRole("button", { name: "继续" });
    expect(button).toHaveClass("h-9", "px-3");
    expect(button).not.toHaveClass("h-10", "px-4");
  });
});
