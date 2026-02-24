import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BookingCard, type BookingProps } from "./BookingCard";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

const defaultDate = new Date("2026-02-15T10:00:00");

const defaultProps: Omit<BookingProps, "id" | "status"> = {
  artisanName: "Jane Artisan",
  service: "Plumbing repair",
  date: defaultDate,
  price: 150,
};

describe("BookingCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the last 8 characters of the booking ID", () => {
    const id = "550e8400-e29b-41d4-a716-446655440000";
    render(
      <BookingCard
        id={id}
        {...defaultProps}
        status="confirmed"
      />
    );
    const card = screen.getByText(defaultProps.service).closest(".group");
    if (card) fireEvent.mouseEnter(card);
    const expectedShortId = id.slice(-8).toUpperCase();
    expect(
      screen.getByText(new RegExp(expectedShortId, "i"))
    ).toBeInTheDocument();
  });

  it("renders in_progress status with violet badge", () => {
    render(
      <BookingCard
        id="test-id"
        {...defaultProps}
        status="in_progress"
      />
    );
    const badge = screen.getByText("in_progress");
    expect(badge.className).toContain("bg-violet-50");
    expect(badge.className).toContain("text-violet-700");
  });

  it.each([
    "pending",
    "confirmed",
    "in_progress",
    "completed",
    "cancelled",
  ] as const)(
    "renders %s badge without undefined classes",
    (status: BookingProps["status"]) => {
      render(
        <BookingCard
          id="test-id"
          {...defaultProps}
          status={status}
        />
      );
      const badge = screen.getByText(status);
      expect(badge.className).not.toContain("undefined");
      expect(badge.className.length).toBeGreaterThan(0);
    }
  );

  it("links View Details to the correct booking page", () => {
    render(
      <BookingCard
        id="abc-123"
        {...defaultProps}
        status="pending"
      />
    );
    const card = screen.getByText(defaultProps.service).closest(".group");
    if (card) fireEvent.mouseEnter(card);
    const link = screen.getByRole("link", { name: /view details/i });
    expect(link).toHaveAttribute("href", "/dashboard/bookings/abc-123");
  });

  it("formats price as XLM by default", () => {
    render(
      <BookingCard
        id="test-id"
        {...defaultProps}
        price={150.5}
        status="pending"
      />
    );
    expect(screen.getByText(/150\.5 XLM/i)).toBeInTheDocument();
  });
});
