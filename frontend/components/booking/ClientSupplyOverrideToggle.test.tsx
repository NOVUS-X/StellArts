import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ClientSupplyOverrideToggle } from "./ClientSupplyOverrideToggle";
import { api } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  api: {
    inventory: {
      setSupplyOverride: vi.fn(),
    },
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const defaultProps = {
  bookingId: "booking-123",
  currentValue: false,
  bookingStatus: "pending",
  token: "test-token",
};

describe("ClientSupplyOverrideToggle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders with label text", () => {
    render(<ClientSupplyOverrideToggle {...defaultProps} />);
    expect(screen.getByText("Client will supply materials")).toBeInTheDocument();
  });

  it("toggle is enabled when booking status is pending", () => {
    render(<ClientSupplyOverrideToggle {...defaultProps} bookingStatus="pending" />);
    expect(screen.getByRole("checkbox")).not.toBeDisabled();
  });

  it("toggle is enabled when booking status is confirmed", () => {
    render(<ClientSupplyOverrideToggle {...defaultProps} bookingStatus="confirmed" />);
    expect(screen.getByRole("checkbox")).not.toBeDisabled();
  });

  it("toggle is disabled when booking status is completed", () => {
    render(<ClientSupplyOverrideToggle {...defaultProps} bookingStatus="completed" />);
    expect(screen.getByRole("checkbox")).toBeDisabled();
  });

  it("toggle is disabled when booking status is cancelled", () => {
    render(<ClientSupplyOverrideToggle {...defaultProps} bookingStatus="cancelled" />);
    expect(screen.getByRole("checkbox")).toBeDisabled();
  });

  it("toggle is disabled when booking status is in_progress", () => {
    render(<ClientSupplyOverrideToggle {...defaultProps} bookingStatus="in_progress" />);
    expect(screen.getByRole("checkbox")).toBeDisabled();
  });

  it("calls api.inventory.setSupplyOverride with correct args on toggle", async () => {
    vi.mocked(api.inventory.setSupplyOverride).mockResolvedValueOnce({
      id: "booking-123",
      client_id: 1,
      artisan_id: 2,
      service: "test",
      date: null,
      estimated_cost: null,
      estimated_hours: null,
      status: "pending",
      location: null,
      notes: null,
      created_at: new Date().toISOString(),
      updated_at: null,
      client_supply_override: true,
    });

    render(<ClientSupplyOverrideToggle {...defaultProps} currentValue={false} />);
    fireEvent.click(screen.getByRole("checkbox"));

    await waitFor(() => {
      expect(api.inventory.setSupplyOverride).toHaveBeenCalledWith(
        "booking-123",
        true,
        "test-token"
      );
    });
  });

  it("calls onToggle callback with new value on success", async () => {
    vi.mocked(api.inventory.setSupplyOverride).mockResolvedValueOnce({
      id: "booking-123",
      client_id: 1,
      artisan_id: 2,
      service: "test",
      date: null,
      estimated_cost: null,
      estimated_hours: null,
      status: "pending",
      location: null,
      notes: null,
      created_at: new Date().toISOString(),
      updated_at: null,
      client_supply_override: true,
    });

    const onToggle = vi.fn();
    render(<ClientSupplyOverrideToggle {...defaultProps} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole("checkbox"));

    await waitFor(() => {
      expect(onToggle).toHaveBeenCalledWith(true);
    });
  });

  it("reflects currentValue prop as initial checked state", () => {
    render(<ClientSupplyOverrideToggle {...defaultProps} currentValue={true} />);
    expect(screen.getByRole("checkbox")).toBeChecked();
  });
});
