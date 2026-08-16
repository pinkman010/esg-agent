import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Skeleton, SkeletonCard, SkeletonTable } from "./skeleton";

describe("Skeleton", () => {
  it("applies shimmer animation class", () => {
    const { container } = render(<Skeleton className="h-4 w-4" />);

    expect(container.firstChild).toHaveClass("animate-shimmer");
  });

  it("renders circle variant", () => {
    const { container } = render(<Skeleton variant="circle" />);

    expect(container.firstChild).toHaveClass("rounded-full");
  });

  it("renders card and table placeholders", () => {
    const { container } = render(
      <>
        <SkeletonCard />
        <SkeletonTable rows={2} />
      </>,
    );

    expect(container.querySelectorAll(".animate-shimmer").length).toBeGreaterThan(0);
  });
});
