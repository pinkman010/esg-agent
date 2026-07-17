import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PdfEvidenceViewer } from "./pdf-evidence-viewer";

describe("PdfEvidenceViewer", () => {
  it("keeps a stable viewport while changing PDF pages", () => {
    render(<PdfEvidenceViewer reportId="report-1" initialPage={6} />);
    const frame = screen.getByTitle("PDF 证据");
    expect(screen.getByText("正在加载 PDF 证据...")).toBeInTheDocument();
    expect(frame).toHaveAttribute("src", expect.stringContaining("#page=6"));
    fireEvent.load(frame);
    expect(screen.queryByText("正在加载 PDF 证据...")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=7"));
    expect(screen.getByText("正在加载 PDF 证据...")).toBeInTheDocument();
  });

  it("shows an explicit PDF load error", () => {
    render(<PdfEvidenceViewer reportId="report-1" initialPage={6} />);

    fireEvent.error(screen.getByTitle("PDF 证据"));

    expect(screen.getByText("PDF 证据加载失败，请检查报告文件。")).toBeInTheDocument();
  });
});
