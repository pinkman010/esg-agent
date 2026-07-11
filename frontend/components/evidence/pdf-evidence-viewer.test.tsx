import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PdfEvidenceViewer } from "./pdf-evidence-viewer";

describe("PdfEvidenceViewer", () => {
  it("keeps a stable viewport while changing PDF pages", () => {
    render(<PdfEvidenceViewer reportId="report-1" initialPage={6} />);
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=6"));
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=7"));
  });
});
