import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ActionCreator } from "./action-creator";

describe("ActionCreator", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("creates an improvement action from the selected requirement", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      action_id: "action-1",
      report_id: "report-1",
      assessment_id: "assessment-1",
      title: "补充 GRI 2-5-a 披露缺口",
      priority: "high",
      status: "open",
      owner_name: "张三",
      due_date: null,
      recommendation_text: "补充以下内容：外部鉴证政策；治理机构和高管参与说明",
      completion_note: null,
      created_by: "张三",
      created_at: null,
      updated_at: null,
    }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(
      <ActionCreator
        reportId="report-1"
        assessmentId="assessment-1"
        requirementId="GRI 2-5-a"
        reviewerName="张三"
        missingItems={["外部鉴证政策", "治理机构和高管参与说明"]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "创建整改任务" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const [url, options] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/reports/report-1/actions");
    expect(JSON.parse(String(options.body))).toMatchObject({
      assessment_id: "assessment-1",
      title: "补充 GRI 2-5-a 披露缺口",
      priority: "high",
      owner_name: "张三",
      recommendation_text: "补充以下内容：外部鉴证政策；治理机构和高管参与说明",
      created_by: "张三",
    });
    expect(await screen.findByText("整改任务已创建")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看整改任务" })).toHaveAttribute("href", "/reports/report-1/actions");
    expect(screen.getByRole("button", { name: "创建整改任务" })).toBeDisabled();
  });
});
