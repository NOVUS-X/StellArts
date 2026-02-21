"use client";

import { Button } from "../ui/button";
import { Card, CardContent } from "../ui/card";
import { Wrench, Zap, Star, ArrowRight } from "lucide-react";
import Link from "next/link";
import Stats from "./Stats";
import { formatCount, useArtisanCounts } from "../../hooks/useArtisanStats";

const FALLBACKS = {
	plumbers: "Near you",
	electricians: "On demand",
	carpenters: "Verified",
	painters: "Top rated",
};

interface SpecialtyCardProps {
	icon: React.ReactNode;
	label: string;
	subtitle: string;
	offsetTop?: boolean;
}

function SpecialtyCard({ icon, label, subtitle, offsetTop = false }: SpecialtyCardProps) {
	return (
		<Card
			className={`bg-white shadow-lg hover:shadow-xl transition-shadow${offsetTop ? " mt-8" : ""
				}`}
		>
			<CardContent className="p-6">
				{icon}
				<div className="text-sm font-medium text-gray-900">{label}</div>
				<div className="text-xs text-gray-500">{subtitle}</div>
			</CardContent>
		</Card>
	);
}


export default function Hero() {
	const { counts, loading } = useArtisanCounts();

	// While loading or when the API fails, fall back to Option A neutral copy.
	// When the API succeeds, use Option B real counts via formatCount().
	const isReady = !loading && counts !== null;

	const plumbers = isReady ? formatCount(counts!.plumbers, FALLBACKS.plumbers) : FALLBACKS.plumbers;
	const electricians = isReady ? formatCount(counts!.electricians, FALLBACKS.electricians) : FALLBACKS.electricians;
	const carpenters = isReady ? formatCount(counts!.carpenters, FALLBACKS.carpenters) : FALLBACKS.carpenters;
	const painters = isReady ? formatCount(counts!.painters, FALLBACKS.painters) : FALLBACKS.painters;

	return (
		<section className="pt-32 pb-20 px-6">
			<div className="container mx-auto max-w-6xl">
				<div className="grid lg:grid-cols-2 gap-12 items-center">

					{/* ── Left column ── */}
					<div className="space-y-8">
						<div className="inline-block">
							<span className="px-4 py-2 bg-blue-50 text-blue-600 rounded-full text-sm font-medium">
								Built on Stellar Blockchain
							</span>
						</div>

						<h1 className="text-5xl lg:text-6xl font-bold text-gray-900 leading-tight">
							Uber for Artisans
							<span className="block text-blue-600 mt-2">Connect. Trust. Transact.</span>
						</h1>

						<p className="text-xl text-gray-600 leading-relaxed">
							A decentralized marketplace platform designed to seamlessly connect
							artisans with clients within their geographical location. Leveraging
							Stellar blockchain for trusted, transparent, and fast transactions.
						</p>

						<div className="flex flex-col sm:flex-row gap-4">
							<Button
								size="lg"
								className="bg-blue-600 hover:bg-blue-700 text-white text-lg px-8"
							>
								<Link href='/artisans'>
									Find an Artisan
									<ArrowRight className='ml-2 w-5 h-5' />
								</Link>
							</Button>
							<Button
								size="lg"
								variant="outline"
								className="border-blue-600 text-blue-600 hover:bg-blue-50 text-lg px-8"
							>
								<Link href='/register?role=artisan'>Join as Artisan</Link>
							</Button>
						</div>

						<Stats />
					</div>

					{/* ── Right column — specialty cards ── */}
					<div className="relative">
						<div className="aspect-square bg-gradient-to-br from-blue-50 to-blue-100 rounded-3xl p-8 flex items-center justify-center">
							<div className="grid grid-cols-2 gap-4 w-full">
								<SpecialtyCard
									icon={<Wrench className="w-8 h-8 text-blue-600 mb-3" />}
									label="Plumbers"
									subtitle={plumbers}
								/>
								<SpecialtyCard
									icon={<Zap className="w-8 h-8 text-blue-600 mb-3" />}
									label="Electricians"
									subtitle={electricians}
									offsetTop
								/>
								<SpecialtyCard
									icon={<Wrench className="w-8 h-8 text-blue-600 mb-3" />}
									label="Carpenters"
									subtitle={carpenters}
								/>
								<SpecialtyCard
									icon={<Star className="w-8 h-8 text-blue-600 mb-3" />}
									label="Painters"
									subtitle={painters}
									offsetTop
								/>
							</div>
						</div>
					</div>

				</div>
			</div>
		</section>
	);
}