"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PlatformStats {
	artisan_count: number;
	completed_bookings: number;
	average_rating: number | null;
}

export default function Stats() {
	const [stats, setStats] = useState<PlatformStats | null>(null);

	useEffect(() => {
		fetch(`${API_BASE}/api/v1/stats/`)
			.then((r) => r.json())
			.then((data) => setStats(data))
			.catch(() => setStats(null));
	}, []);

	return (
		<div className='flex items-center space-x-8 pt-4'>
			<div>
				<div className='text-3xl font-bold text-gray-900'>
					{stats ? `${stats.artisan_count}+` : "\u2014"}
				</div>
				<div className='text-sm text-gray-600'>Active Artisans</div>
			</div>
			<div>
				<div className='text-3xl font-bold text-gray-900'>
					{stats ? `${stats.completed_bookings}+` : "\u2014"}
				</div>
				<div className='text-sm text-gray-600'>Jobs Completed</div>
			</div>
			<div>
				<div className='text-3xl font-bold text-gray-900'>
					{stats?.average_rating
						? `${stats.average_rating.toFixed(1)}\u2605`
						: "New"}
				</div>
				<div className='text-sm text-gray-600'>Average Rating</div>
			</div>
		</div>
	);
}
