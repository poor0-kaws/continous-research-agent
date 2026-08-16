import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("uses plain language for a contested result", () => {
    render(<StatusBadge status="contested" />);
    expect(screen.getByText("Sources disagree")).toBeInTheDocument();
  });
});
