"use client";

import { usePlatformStats } from "../../hooks/useArtisanStats";

const FALLBACK = {
	artisans: { value: "Fast", label: "Booking in minutes" },
	bookings: { value: "Secure", label: "Stellar escrow" },
	rating: { value: "Trusted", label: "On-chain ratings" },
};

interface StatItemProps {
	value: string;
	label: string;
}

function StatItem({ value, label }: StatItemProps) {
	return (
		<div>
			<div className="text-3xl font-bold text-gray-900">{value}</div>
			<div className="text-sm text-gray-600">{label}</div>
		</div>
	);
}


export default function Stats() {
	const { stats, loading } = usePlatformStats();

	// While loading or when the API fails → Option A fallback copy.
	// When the API succeeds → Option B real numbers.
	const isReady = !loading && stats !== null;

	const artisanValue = isReady
		? `${stats!.artisan_count}+`
		: FALLBACK.artisans.value;

	const artisanLabel = isReady ? "Active Artisans" : FALLBACK.artisans.label;

	const bookingsValue = isReady
		? `${stats!.completed_bookings}+`
		: FALLBACK.bookings.value;

	const bookingsLabel = isReady ? "Jobs Completed" : FALLBACK.bookings.label;

	const ratingValue = isReady
		? stats!.average_rating
			? `${stats!.average_rating.toFixed(1)}★`
			: "New"
		: FALLBACK.rating.value;

	const ratingLabel = isReady ? "Average Rating" : FALLBACK.rating.label;

	return (
		<div className="flex items-center space-x-8 pt-4">
			<StatItem value={artisanValue} label={artisanLabel} />
			<StatItem value={bookingsValue} label={bookingsLabel} />
			<StatItem value={ratingValue} label={ratingLabel} />
		</div>
	);
}