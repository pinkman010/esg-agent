import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { PdfEvidenceViewer } from "./pdf-evidence-viewer";

describe("PdfEvidenceViewer", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps a stable viewport while changing PDF pages", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ page_count: 78 }), {
      status: 200,
      headers: { "content-type": "application/json" },
    })));
    renderWithQuery(<PdfEvidenceViewer reportId="report-1" initialPage={6} />);
    const frame = screen.getByTitle("PDF 证据");
    expect(frame).not.toHaveAttribute("download");
    expect(screen.getByText("正在加载 PDF 证据...")).toBeInTheDocument();
    expect(frame).toHaveAttribute("src", expect.stringContaining("/pages/6/image"));
    fireEvent.load(frame);
    expect(screen.queryByText("正在加载 PDF 证据...")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("/pages/7/image"));
    expect(screen.getByText("正在加载 PDF 证据...")).toBeInTheDocument();
  });

  it("shows an explicit PDF load error", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ page_count: 78 }), {
      status: 200,
      headers: { "content-type": "application/json" },
    })));
    renderWithQuery(<PdfEvidenceViewer reportId="report-1" initialPage={6} />);

    fireEvent.error(screen.getByTitle("PDF 证据"));

    expect(screen.getByText("PDF 证据加载失败，请检查报告文件。")).toBeInTheDocument();
    const failedSrc = screen.getByTitle("PDF 证据").getAttribute("src");
    fireEvent.click(screen.getByRole("button", { name: "重试加载 PDF 证据" }));
    expect(screen.getByTitle("PDF 证据").getAttribute("src")).not.toBe(failedSrc);
  });

  it("supports zoom controls and respects the report page limit", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ page_count: 6 }), {
      status: 200,
      headers: { "content-type": "application/json" },
    })));
    renderWithQuery(<PdfEvidenceViewer reportId="report-1" initialPage={6} />);

    await waitFor(() => expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled());
    const frame = screen.getByTitle("PDF 证据");
    expect(frame).toHaveStyle({ width: "100%" });
    fireEvent.click(screen.getByRole("button", { name: "放大 PDF" }));
    expect(frame).toHaveStyle({ width: "125%" });
    fireEvent.click(screen.getByRole("button", { name: "缩小 PDF" }));
    expect(frame).toHaveStyle({ width: "100%" });
    fireEvent.click(screen.getByRole("button", { name: "恢复适合宽度" }));
    expect(frame).toHaveStyle({ width: "100%" });
  });
});
