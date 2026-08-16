import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Select } from "./select";

describe("Select", () => {
  it("associates its label with a native keyboard-accessible combobox", () => {
    const onChange = vi.fn();
    render(
      <Select
        label="复核状态"
        value="all"
        options={["all", "reviewed"]}
        format={(value) => (value === "all" ? "全部" : "已复核")}
        onChange={onChange}
      />,
    );

    const combobox = screen.getByRole("combobox", { name: "复核状态" });
    fireEvent.change(combobox, { target: { value: "reviewed" } });

    expect(onChange).toHaveBeenCalledWith("reviewed");
  });
});
