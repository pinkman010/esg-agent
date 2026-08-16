import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Panel } from "./panel";

describe("Panel", () => {
  it("renders title and children", () => {
    render(
      <Panel title="核查结果">
        <p>内容</p>
      </Panel>,
    );

    expect(screen.getByRole("heading", { name: "核查结果" })).toBeInTheDocument();
    expect(screen.getByText("内容")).toBeInTheDocument();
  });

  it("renders without title", () => {
    render(<Panel>仅内容</Panel>);

    expect(screen.getByText("仅内容")).toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });

  it("gives each information trigger an accessible name and unique tooltip target", () => {
    render(
      <>
        <Panel title="核查结果" showInfo infoTip="结果说明">内容一</Panel>
        <Panel title="复核工作量" showInfo infoTip="工作量说明">内容二</Panel>
      </>,
    );

    const firstTrigger = screen.getByRole("button", { name: "查看核查结果说明" });
    const secondTrigger = screen.getByRole("button", { name: "查看复核工作量说明" });
    expect(firstTrigger).toHaveAttribute("aria-controls");
    expect(secondTrigger).toHaveAttribute("aria-controls");
    expect(firstTrigger.getAttribute("aria-controls")).not.toBe(secondTrigger.getAttribute("aria-controls"));
  });
});
