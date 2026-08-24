import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReportPageHero } from "./report-page-hero";

describe("ReportPageHero", () => {
  it("renders a static decorative report hero by default", () => {
    const { container } = render(
      <ReportPageHero
        eyebrow="报告核查清单"
        title="完整 GRI 核查范围"
        description="核查说明"
        imageSrc="/visuals/module-policy-disclosure.webp"
        imagePosition="28% 50%"
        meta={<span>共 577 项</span>}
        action={<button type="button">进入页面</button>}
      />,
    );

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "完整 GRI 核查范围",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("共 577 项")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入页面" })).toBeInTheDocument();
    const artwork = container.querySelector(
      'img[src*="module-policy-disclosure"]',
    );
    expect(artwork).toHaveAttribute("alt", "");
    expect(artwork).toHaveAttribute("loading", "eager");
    expect(artwork).toHaveClass("opacity-[0.23]");
    expect(artwork).not.toHaveClass("animate-ken-burns");
    expect(artwork).toHaveStyle({ objectPosition: "28% 50%" });
    expect(container.querySelector('[class*="linear-gradient"]')).toBeNull();
  });

  it("only enables the image motion when requested", () => {
    const { container } = render(
      <ReportPageHero
        eyebrow="当前报告"
        title="报告总览"
        imageSrc="/visuals/module-policy-disclosure.webp"
        animated
      />,
    );

    expect(container.querySelector("img")).toHaveClass("animate-ken-burns");
  });
});
