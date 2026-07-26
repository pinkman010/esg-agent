import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewerGate } from "./reviewer-gate";
import { renderWithQuery } from "@/tests/render-with-query";

describe("ReviewerGate", () => {
  beforeEach(() => localStorage.clear());

  it("remembers the reviewer name for the next review session", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [],
      page: 1,
      page_size: 50,
      total: 0,
    }), { status: 200, headers: { "content-type": "application/json" } })));
    const first = renderWithQuery(<ReviewerGate reportId="report-1" />);
    fireEvent.change(screen.getByRole("textbox", { name: "复核人名称" }), {
      target: { value: "张三" },
    });
    fireEvent.click(screen.getByRole("button", { name: "进入复核工作台" }));
    expect(localStorage.getItem("esg-agent-reviewer-name")).toBe("张三");

    first.unmount();
    renderWithQuery(<ReviewerGate reportId="report-2" />);
    expect(screen.getByRole("textbox", { name: "复核人名称" })).toHaveValue("张三");
  });
});
