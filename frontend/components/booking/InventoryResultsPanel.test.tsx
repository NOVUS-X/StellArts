import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { InventoryResultsPanel } from "./InventoryResultsPanel";
import type { InventoryCheckResult } from "../../lib/api";

const baseResult: InventoryCheckResult = {
  id: "result-1",
  booking_id: "booking-1",
  bom_item_id: "bom-1",
  store_id: "store-1",
  store_name: "Hardware Plus",
  store_address: "123 Main St",
  available: true,
  pre_pay_url: null,
  status: "fresh",
  checked_at: new Date().toISOString(),
};

describe("InventoryResultsPanel", () => {
  it("renders empty state when results list is empty", () => {
    render(<InventoryResultsPanel results={[]} />);
    expect(screen.getByText("No inventory data yet")).toBeInTheDocument();
  });

  it("does not render empty state when results are present", () => {
    render(<InventoryResultsPanel results={[baseResult]} />);
    expect(screen.queryByText("No inventory data yet")).not.toBeInTheDocument();
  });

  it("renders store name for each result", () => {
    render(<InventoryResultsPanel results={[baseResult]} />);
    expect(screen.getByText("Hardware Plus")).toBeInTheDocument();
  });

  it("shows Available badge when result is available", () => {
    render(<InventoryResultsPanel results={[baseResult]} />);
    expect(screen.getByText("Available")).toBeInTheDocument();
  });

  it("shows Unavailable badge when result is not available", () => {
    const result = { ...baseResult, available: false };
    render(<InventoryResultsPanel results={[result]} />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("shows Stale badge when status is stale", () => {
    const result = { ...baseResult, status: "stale" };
    render(<InventoryResultsPanel results={[result]} />);
    expect(screen.getByText("Stale")).toBeInTheDocument();
  });

  it("does not show Stale badge when status is not stale", () => {
    render(<InventoryResultsPanel results={[baseResult]} />);
    expect(screen.queryByText("Stale")).not.toBeInTheDocument();
  });

  it("renders pre-pay link with correct href when pre_pay_url is set", () => {
    const result = { ...baseResult, pre_pay_url: "https://store.example.com/pay/123" };
    render(<InventoryResultsPanel results={[result]} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://store.example.com/pay/123");
  });

  it("does not render pre-pay link when pre_pay_url is null", () => {
    render(<InventoryResultsPanel results={[baseResult]} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
