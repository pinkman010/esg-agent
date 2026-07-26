import { describe, expect, it } from "vitest";

import { reportIdFromPath } from "./report-route";

describe("reportIdFromPath", () => {
  it("extracts the report id from report-scoped routes", () => {
    expect(reportIdFromPath("/reports/report-1/dashboard")).toBe("report-1");
    expect(reportIdFromPath("/reports/report-1/review")).toBe("report-1");
    expect(reportIdFromPath("/reports/report%20one/actions")).toBe("report one");
  });

  it("ignores global and compatibility routes", () => {
    expect(reportIdFromPath("/reports")).toBeNull();
    expect(reportIdFromPath("/runs/run-1")).toBeNull();
    expect(reportIdFromPath("/review")).toBeNull();
  });
});
