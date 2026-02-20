"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "../../../components/ui/Navbar";
import Footer from "../../../components/ui/Footer";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { useAuth } from "../../../context/AuthContext";
import { useWallet } from "../../../context/WalletContext";
import { ArrowLeft, Wallet } from "lucide-react";

export default function DashboardPaymentsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const { isConnected, address, connect } = useWallet();

  if (!isLoading && !isAuthenticated) {
    router.replace("/login?redirect=/dashboard/payments");
    return null;
  }

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="pt-24 pb-16 px-4 max-w-4xl mx-auto">
        <Link
          href="/dashboard"
          className="inline-flex items-center text-gray-600 hover:text-blue-600 mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Dashboard
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Payments</h1>
        <p className="text-gray-600 mb-8">
          Fund escrow, release payments, and view payment history.
        </p>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wallet className="w-5 h-5" />
              Stellar wallet
            </CardTitle>
            <CardDescription>
              Connect your wallet to fund escrow and release payments to
              artisans.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isConnected && address ? (
              <p className="text-sm font-mono text-gray-700 bg-gray-100 px-3 py-2 rounded-md">
                Connected: {address.slice(0, 8)}…{address.slice(-8)}
              </p>
            ) : (
              <button
                type="button"
                onClick={connect}
                className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
              >
                Connect wallet
              </button>
            )}
          </CardContent>
        </Card>

        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Payment history</CardTitle>
            <CardDescription>
              Escrow and release history will appear here once the payment API
              is wired (build-hold / submit flow).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">No payments yet.</p>
          </CardContent>
        </Card>
      </main>
      <Footer />
    </div>
  );
}
