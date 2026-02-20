import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Stats from "../../components/home/Stats";

describe("Stats — platform statistics bar", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    // ── Test 1: No fabricated numbers ever render ─────────────────────────────

    it("never renders hardcoded fabricated counts", async () => {
        vi.spyOn(global, "fetch").mockRejectedValue(new Error("Network error"));

        render(<Stats />);

        expect(screen.queryByText("10K+")).not.toBeInTheDocument();
        expect(screen.queryByText("50K+")).not.toBeInTheDocument();
        expect(screen.queryByText("4.8★")).not.toBeInTheDocument();
    });

    // ── Test 2: Option A fallback shown when API errors ───────────────────────

    it("shows Option A feature-benefit copy when API returns an error", async () => {
        vi.spyOn(global, "fetch").mockRejectedValue(new Error("Network error"));

        render(<Stats />);

        await waitFor(() => {
            expect(screen.getByText("Fast")).toBeInTheDocument();
            expect(screen.getByText("Secure")).toBeInTheDocument();
            expect(screen.getByText("Trusted")).toBeInTheDocument();
            expect(screen.getByText("Booking in minutes")).toBeInTheDocument();
            expect(screen.getByText("Stellar escrow")).toBeInTheDocument();
            expect(screen.getByText("On-chain ratings")).toBeInTheDocument();
        });
    });

    // ── Test 3: Option B real stats shown when API succeeds ──────────────────

    it("renders fetched stats when the backend responds successfully", async () => {
        vi.spyOn(global, "fetch").mockResolvedValue({
            ok: true,
            json: () =>
                Promise.resolve({
                    artisan_count: 47,
                    completed_bookings: 12,
                    average_rating: 4.2,
                }),
        } as Response);

        render(<Stats />);

        await waitFor(() => {
            expect(screen.getByText("47+")).toBeInTheDocument();
            expect(screen.getByText("12+")).toBeInTheDocument();
            expect(screen.getByText("4.2★")).toBeInTheDocument();
            expect(screen.getByText("Active Artisans")).toBeInTheDocument();
            expect(screen.getByText("Jobs Completed")).toBeInTheDocument();
            expect(screen.getByText("Average Rating")).toBeInTheDocument();
        });
    });

    // ── Test 4: "New" shown when API returns null average_rating ─────────────

    it("shows 'New' for average rating when the API returns null", async () => {
        vi.spyOn(global, "fetch").mockResolvedValue({
            ok: true,
            json: () =>
                Promise.resolve({
                    artisan_count: 3,
                    completed_bookings: 1,
                    average_rating: null,
                }),
        } as Response);

        render(<Stats />);

        await waitFor(() => {
            expect(screen.getByText("New")).toBeInTheDocument();
        });
    });

    // ── Test 5: Option A fallback shown while API is still loading ────────────

    it("shows Option A feature-benefit copy while the API request is in-flight", () => {

        vi.spyOn(global, "fetch").mockReturnValue(new Promise(() => { }));

        render(<Stats />);

        expect(screen.getByText("Fast")).toBeInTheDocument();
        expect(screen.getByText("Secure")).toBeInTheDocument();
        expect(screen.getByText("Trusted")).toBeInTheDocument();
    });
});