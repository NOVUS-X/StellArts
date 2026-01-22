"use client";

import Navbar from "../components/ui/Navbar";
import Footer from "../components/ui/Footer";
import Hero from "../components/home/Hero";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import {
	MapPin,
	Shield,
	Zap,
	Star,
	Globe,
	DollarSign,
	Users,
	Wrench,
	ArrowRight,
} from "lucide-react";

export default function Home() {
	const features = [
		{
			icon: MapPin,
			title: "Artisan Discovery",
			description:
				"Search and book artisans within your area, filtered by skills, ratings, and availability.",
		},
		{
			icon: Users,
			title: "Geolocation Matching",
			description:
				"Uber-like system that intelligently maps clients to nearby artisans.",
		},
		{
			icon: Shield,
			title: "Secure Escrow Payments",
			description:
				"Clients deposit payments into escrow. Funds are released automatically once work is confirmed.",
		},
		{
			icon: Star,
			title: "Reputation & Reviews",
			description:
				"Ratings and feedback stored immutably to help build trust in the community.",
		},
		{
			icon: Globe,
			title: "Multi-currency Support",
			description:
				"Transact in your preferred local currency or stablecoin using Stellar's built-in DEX.",
		},
		{
			icon: Zap,
			title: "Low Fees & Fast Settlement",
			description:
				"Near-instant payments with minimal transaction costs powered by Stellar.",
		},
	];

	const useCases = [
		{
			icon: Wrench,
			title: "Urban Communities",
			description:
				"Quick discovery of trusted artisans for emergency home repairs.",
		},
		{
			icon: MapPin,
			title: "Small Towns",
			description: "Artisans gain visibility beyond personal networks.",
		},
		{
			icon: Globe,
			title: "Cross-border Work",
			description:
				"Migrant artisans can get verified and receive fair payments securely.",
		},
	];

	const whyStellar = [
		{
			icon: Shield,
			title: "Escrow & Smart Contracts",
			description: "Enables trustless transactions between strangers.",
		},
		{
			icon: DollarSign,
			title: "Low Transaction Costs",
			description: "Affordable even for micro-payments.",
		},
		{
			icon: Zap,
			title: "Fast Settlement",
			description: "Near-instant confirmation of bookings and payments.",
		},
		{
			icon: Users,
			title: "Financial Inclusion",
			description:
				"Accessible via mobile wallets, especially in emerging markets.",
		},
	];

	return (
		<div className='min-h-screen bg-white'>
			<Navbar />

			<main>
				<Hero />

				<section
					className='py-20 bg-gray-50'
					id='features'>
					<div className='container mx-auto px-6 max-w-6xl'>
						<div className='text-center mb-16'>
							<span className='text-blue-600 font-semibold text-sm uppercase tracking-wide'>
								Features
							</span>
							<h2 className='text-4xl font-bold text-gray-900 mt-4'>
								Everything You Need
							</h2>
							<p className='text-xl text-gray-600 mt-4 max-w-2xl mx-auto'>
								Powerful features designed to create trust,
								transparency, and seamless transactions
							</p>
						</div>
						<div className='grid md:grid-cols-2 lg:grid-cols-3 gap-8'>
							{features.map((feature, index) => (
								<Card
									key={index}
									className='bg-white border-none shadow-lg hover:shadow-xl transition-all hover:-translate-y-1'>
									<CardContent className='p-8'>
										<div className='w-14 h-14 bg-blue-100 rounded-2xl flex items-center justify-center mb-6'>
											<feature.icon className='w-7 h-7 text-blue-600' />
										</div>
										<h3 className='text-xl font-bold text-gray-900 mb-3'>
											{feature.title}
										</h3>
										<p className='text-gray-600 leading-relaxed'>
											{feature.description}
										</p>
									</CardContent>
								</Card>
							))}
						</div>
					</div>
				</section>

				<section
					className='py-20 bg-blue-600'
					id='use-cases'>
					<div className='container mx-auto px-6 max-w-6xl'>
						<div className='text-center mb-16'>
							<span className='text-blue-200 font-semibold text-sm uppercase tracking-wide'>
								Use Cases
							</span>
							<h2 className='text-4xl font-bold text-white mt-4'>
								Who Benefits from Stellarts?
							</h2>
							<p className='text-xl text-blue-100 mt-4 max-w-2xl mx-auto'>
								Empowering communities across different settings
							</p>
						</div>
						<div className='grid md:grid-cols-3 gap-8'>
							{useCases.map((useCase, index) => (
								<Card
									key={index}
									className='bg-white/10 backdrop-blur-sm border-white/20 hover:bg-white/20 transition-all'>
									<CardContent className='p-8'>
										<div className='w-14 h-14 bg-white rounded-2xl flex items-center justify-center mb-6'>
											<useCase.icon className='w-7 h-7 text-blue-600' />
										</div>
										<h3 className='text-xl font-bold text-white mb-3'>
											{useCase.title}
										</h3>
										<p className='text-blue-100 leading-relaxed'>
											{useCase.description}
										</p>
									</CardContent>
								</Card>
							))}
						</div>
					</div>
				</section>

				<section
					className='py-20 bg-white'
					id='why-stellar'>
					<div className='container mx-auto px-6 max-w-6xl'>
						<div className='text-center mb-16'>
							<span className='text-blue-600 font-semibold text-sm uppercase tracking-wide'>
								Technology
							</span>
							<h2 className='text-4xl font-bold text-gray-900 mt-4'>
								Why Stellar Blockchain?
							</h2>
							<p className='text-xl text-gray-600 mt-4 max-w-2xl mx-auto'>
								Built on enterprise-grade blockchain technology for
								security and speed
							</p>
						</div>
						<div className='grid md:grid-cols-2 gap-8'>
							{whyStellar.map((reason, index) => (
								<Card
									key={index}
									className='bg-gradient-to-br from-gray-50 to-blue-50 border-none shadow-lg'>
									<CardContent className='p-8'>
										<div className='flex items-start space-x-4'>
											<div className='w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0'>
												<reason.icon className='w-6 h-6 text-white' />
											</div>
											<div>
												<h3 className='text-xl font-bold text-gray-900 mb-2'>
													{reason.title}
												</h3>
												<p className='text-gray-600 leading-relaxed'>
													{reason.description}
												</p>
											</div>
										</div>
									</CardContent>
								</Card>
							))}
						</div>
					</div>
				</section>

				<section className='py-20 bg-gradient-to-br from-blue-600 to-blue-700'>
					<div className='container mx-auto px-6 max-w-4xl text-center'>
						<h2 className='text-4xl font-bold text-white mb-6'>
							Ready to Get Started?
						</h2>
						<p className='text-xl text-blue-100 mb-10 max-w-2xl mx-auto'>
							Join thousands of artisans and clients building trust
							through decentralized transactions
						</p>
						<div className='flex flex-col sm:flex-row gap-4 justify-center'>
							<Button
								size='lg'
								className='bg-white text-blue-600 hover:bg-gray-100 text-lg px-8'>
								Get Started Now
								<ArrowRight className='ml-2 w-5 h-5' />
							</Button>
							<Button
								size='lg'
								variant='outline'
								className='border-white text-white hover:bg-white/10 text-lg px-8'>
								View Documentation
							</Button>
						</div>
					</div>
				</section>
			</main>

			<Footer />
		</div>
	);
}
