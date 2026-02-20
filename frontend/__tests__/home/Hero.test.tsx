import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Hero from "../../components/home/Hero";

// ---------------------------------------------------------------------------
// Mock the Stats child so Hero tests are isolated
// ---------------------------------------------------------------------------
vi.mock("@/components/home/Stats", () => ({
    default: () => <div data-testid="stats-mock" />,
}));

// ---------------------------------------------------------------------------
// Mock next/navigation if used transitively (safe no-op)
// ---------------------------------------------------------------------------
vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
}));

describe("Hero — specialty cards", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    // ── Test 1: No hardcoded numbers ever render ──────────────────────────────

    it("never renders hardcoded availability numbers regardless of API state", async () => {
        // API fails — Option A fallback should be used
        vi.spyOn(global, "fetch").mockRejectedValue(new Error("Network error"));

        render(<Hero />);

        // These hardcoded strings must NEVER appear
        expect(screen.queryByText("2,345 available")).not.toBeInTheDocument();
        expect(screen.queryByText("1,892 available")).not.toBeInTheDocument();
        expect(screen.queryByText("1,567 available")).not.toBeInTheDocument();
        expect(screen.queryByText("1,234 available")).not.toBeInTheDocument();
    });

    // ── Test 2: Option A fallback shown when API errors ───────────────────────

    it("shows Option A neutral copy when the API returns an error", async () => {
        vi.spyOn(global, "fetch").mockRejectedValue(new Error("Network error"));

        render(<Hero />);

        await waitFor(() => {
            expect(screen.getByText("Near you")).toBeInTheDocument();
            expect(screen.getByText("On demand")).toBeInTheDocument();
            expect(screen.getByText("Verified")).toBeInTheDocument();
            expect(screen.getByText("Top rated")).toBeInTheDocument();
        });
    });

    // ── Test 3: Option B real counts shown when API succeeds ─────────────────

    it("shows real API counts when the backend responds successfully", async () => {
        vi.spyOn(global, "fetch").mockResolvedValue({
            ok: true,
            json: () =>
                Promise.resolve({
                    plumbers: 47,
                    electricians: 31,
                    carpenters: 12,
                    painters: 5,
                }),
        } as Response);

        render(<Hero />);

        await waitFor(() => {
            expect(screen.getByText("47 available")).toBeInTheDocument();
            expect(screen.getByText("31 available")).toBeInTheDocument();
            expect(screen.getByText("12 available")).toBeInTheDocument();
            expect(screen.getByText("5 available")).toBeInTheDocument();
        });
    });

    // ── Test 4: "Coming soon" shown when API returns zero counts ─────────────

    it("shows 'Coming soon' for a specialty when count is 0", async () => {
        vi.spyOn(global, "fetch").mockResolvedValue({
            ok: true,
            json: () =>
                Promise.resolve({
                    plumbers: 0,
                    electricians: 0,
                    carpenters: 0,
                    painters: 0,
                }),
        } as Response);

        render(<Hero />);

        await waitFor(() => {
            const comingSoonItems = screen.getAllByText("Coming soon");
            expect(comingSoonItems).toHaveLength(4);
        });
    });

    // ── Test 5: Option A fallback shown while API is still loading ────────────

    it("shows Option A neutral copy while the API request is in-flight", () => {
        // Never resolves — simulates a pending request
        vi.spyOn(global, "fetch").mockReturnValue(new Promise(() => { }));

        render(<Hero />);

        expect(screen.getByText("Near you")).toBeInTheDocument();
        expect(screen.getByText("On demand")).toBeInTheDocument();
        expect(screen.getByText("Verified")).toBeInTheDocument();
        expect(screen.getByText("Top rated")).toBeInTheDocument();
    });
});