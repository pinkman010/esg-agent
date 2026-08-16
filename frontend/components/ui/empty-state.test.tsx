import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "./empty-state";

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(<EmptyState title="暂无数据" description="请先上传报告" variant="data" />);

    expect(screen.getByText("暂无数据")).toBeInTheDocument();
    expect(screen.getByText("请先上传报告")).toBeInTheDocument();
  });

  it("calls onReset when reset button is clicked", () => {
    const onReset = vi.fn();
    render(<EmptyState onReset={onReset} />);

    fireEvent.click(screen.getByRole("button", { name: "重置筛选条件" }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("hides reset button without onReset", () => {
    render(<EmptyState />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
