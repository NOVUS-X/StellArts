import { Button } from "../ui/button";
import { Card, CardContent } from "../ui/card";
import { Wrench, Zap, Star, ArrowRight } from "lucide-react";
import Stats from "./Stats";

export default function Hero() {
	return (
		<section className='pt-32 pb-20 px-6'>
			<div className='container mx-auto max-w-6xl'>
				<div className='grid lg:grid-cols-2 gap-12 items-center'>
					<div className='space-y-8'>
						<div className='inline-block'>
							<span className='px-4 py-2 bg-blue-50 text-blue-600 rounded-full text-sm font-medium'>
								Built on Stellar Blockchain
							</span>
						</div>
						<h1 className='text-5xl lg:text-6xl font-bold text-gray-900 leading-tight'>
							Uber for Artisans
							<span className='block text-blue-600 mt-2'>
								Connect. Trust. Transact.
							</span>
						</h1>
						<p className='text-xl text-gray-600 leading-relaxed'>
							A decentralized marketplace platform designed to seamlessly
							connect artisans with clients within their geographical
							location. Leveraging Stellar blockchain for trusted,
							transparent, and fast transactions.
						</p>
						<div className='flex flex-col sm:flex-row gap-4'>
							<Button
								size='lg'
								className='bg-blue-600 hover:bg-blue-700 text-white text-lg px-8'>
								Find an Artisan
								<ArrowRight className='ml-2 w-5 h-5' />
							</Button>
							<Button
								size='lg'
								variant='outline'
								className='border-blue-600 text-blue-600 hover:bg-blue-50 text-lg px-8'>
								Join as Artisan
							</Button>
						</div>
						<Stats />
					</div>
					<div className='relative'>
						<div className='aspect-square bg-gradient-to-br from-blue-50 to-blue-100 rounded-3xl p-8 flex items-center justify-center'>
							<div className='grid grid-cols-2 gap-4 w-full'>
								<Card className='bg-white shadow-lg hover:shadow-xl transition-shadow'>
									<CardContent className='p-6'>
										<Wrench className='w-8 h-8 text-blue-600 mb-3' />
										<div className='text-sm font-medium text-gray-900'>
											Plumbers
										</div>
										<div className='text-xs text-gray-500'>
											2,345 available
										</div>
									</CardContent>
								</Card>
								<Card className='bg-white shadow-lg hover:shadow-xl transition-shadow mt-8'>
									<CardContent className='p-6'>
										<Zap className='w-8 h-8 text-blue-600 mb-3' />
										<div className='text-sm font-medium text-gray-900'>
											Electricians
										</div>
										<div className='text-xs text-gray-500'>
											1,892 available
										</div>
									</CardContent>
								</Card>
								<Card className='bg-white shadow-lg hover:shadow-xl transition-shadow'>
									<CardContent className='p-6'>
										<Wrench className='w-8 h-8 text-blue-600 mb-3' />
										<div className='text-sm font-medium text-gray-900'>
											Carpenters
										</div>
										<div className='text-xs text-gray-500'>
											1,567 available
										</div>
									</CardContent>
								</Card>
								<Card className='bg-white shadow-lg hover:shadow-xl transition-shadow mt-8'>
									<CardContent className='p-6'>
										<Star className='w-8 h-8 text-blue-600 mb-3' />
										<div className='text-sm font-medium text-gray-900'>
											Painters
										</div>
										<div className='text-xs text-gray-500'>
											1,234 available
										</div>
									</CardContent>
								</Card>
							</div>
						</div>
					</div>
				</div>
			</div>
		</section>
	);
}
