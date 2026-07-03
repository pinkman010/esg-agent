import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DisclosureSummaryChart } from "./disclosure-summary-chart";

describe("DisclosureSummaryChart", () => {
  it("renders business verdict totals", () => {
    render(
      <DisclosureSummaryChart
        assessments={[
          { verdict: "disclosed" },
          { verdict: "disclosed" },
          { verdict: "unknown" },
        ]}
      />,
    );

    expect(screen.getByText("disclosed")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("unknown")).toBeInTheDocument();
  });
});