"use client";

import { useState, useEffect } from "react";
import { 
  Wallet, 
  History, 
  ArrowUpRight, 
  ArrowDownLeft, 
  ExternalLink,
  ShieldCheck,
  AlertCircle,
  Loader2
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import Price from "../../../components/ui/Price";
import { useAuth } from "../../../context/AuthContext";
import { useWallet } from "../../../context/WalletContext";
import { api, type PaymentOut, type BookingResponse } from "../../../lib/api";
import { cn } from "../../../lib/utils";
import PaymentModal from "../../../components/dashboard/PaymentModal";

export default function DashboardPaymentsPage() {
  const { token } = useAuth();
  const { isConnected, address, connect, disconnect } = useWallet();
  
  const [payments, setPayments] = useState<PaymentOut[]>([]);
  const [pendingBookings, setPendingBookings] = useState<BookingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBooking, setSelectedBooking] = useState<BookingResponse | null>(null);

  useEffect(() => {
    if (!token) return;
    loadData();
  }, [token]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [paymentsData, bookingsData] = await Promise.all([
        api.payments.myPayments(token!),
        api.bookings.myBookings(token!)
      ]);
      setPayments(paymentsData);
      // Filter bookings that are confirmed and don't have a HELD/FUNDED payment yet
      // For simplicity, we just show confirmed bookings
      setPendingBookings(bookingsData.filter(b => b.status === "confirmed"));
    } catch (err) {
      console.error("Failed to load payment data:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Payments</h1>
        <p className="text-gray-500">Manage your wallet and track escrow transactions</p>
      </div>

      {/* Wallet Card */}
      <Card className="border-none shadow-sm bg-gradient-to-br from-gray-900 to-blue-900 text-white overflow-hidden relative">
        <div className="absolute top-0 right-0 p-8 opacity-10">
          <Wallet className="w-32 h-32" />
        </div>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white/90">
            <Wallet className="w-5 h-5" />
            Stellar Wallet
          </CardTitle>
          <CardDescription className="text-white/60">
            {isConnected ? "Connected to Stellar Testnet" : "Connect your wallet to manage funds"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isConnected ? (
            <div className="space-y-6">
              <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/10">
                <p className="text-xs text-white/50 uppercase tracking-wider font-bold mb-1">Account Address</p>
                <p className="text-sm font-mono break-all text-blue-100">{address}</p>
              </div>
              <Button 
                variant="outline" 
                className="bg-transparent border-white/20 text-white hover:bg-white/10 rounded-xl"
                onClick={disconnect}
              >
                Disconnect Wallet
              </Button>
            </div>
          ) : (
            <Button 
              className="bg-white text-blue-900 hover:bg-blue-50 rounded-xl px-8 py-6 text-lg font-bold shadow-xl shadow-blue-900/20"
              onClick={connect}
            >
              Connect Wallet
            </Button>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Pending Payments */}
        <div className="lg:col-span-1 space-y-4">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-amber-500" />
            Action Required
          </h2>
          {loading ? (
            <div className="space-y-3">
              <div className="h-24 bg-gray-100 rounded-2xl animate-pulse" />
              <div className="h-24 bg-gray-100 rounded-2xl animate-pulse" />
            </div>
          ) : pendingBookings.length === 0 ? (
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center">
              <p className="text-sm text-gray-500">No pending payments needed</p>
            </div>
          ) : (
            <div className="space-y-3">
              {pendingBookings.map((booking) => (
                <div key={booking.id} className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <p className="text-xs font-bold text-blue-600 uppercase mb-1">Confirmed</p>
                      <h3 className="text-sm font-bold text-gray-900 truncate max-w-[150px]">{booking.service}</h3>
                    </div>
                    <div className="text-right">
                      <Price amount={booking.estimated_cost || 0} />
                    </div>
                  </div>
                  <Button 
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 text-sm h-auto"
                    onClick={() => setSelectedBooking(booking)}
                  >
                    Pay Now
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Payment History */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <History className="w-5 h-5 text-blue-600" />
            Payment History
          </h2>
          <Card className="border-gray-100 shadow-sm overflow-hidden rounded-2xl">
            <CardContent className="p-0">
              {loading ? (
                <div className="p-8 space-y-4">
                  {[1, 2, 3].map(i => (
                    <div key={i} className="h-12 bg-gray-50 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : payments.length === 0 ? (
                <div className="p-12 text-center">
                  <div className="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-3">
                    <History className="w-6 h-6 text-gray-300" />
                  </div>
                  <p className="text-sm text-gray-500">No payment history found</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-50">
                  {payments.map((payment) => (
                    <div key={payment.id} className="p-4 flex items-center justify-between hover:bg-gray-50/50 transition-colors">
                      <div className="flex items-center gap-4">
                        <div className={cn(
                          "w-10 h-10 rounded-full flex items-center justify-center",
                          payment.status === "released" ? "bg-green-100 text-green-600" : 
                          payment.status === "held" ? "bg-blue-100 text-blue-600" : "bg-gray-100 text-gray-600"
                        )}>
                          {payment.status === "released" ? <ArrowUpRight className="w-5 h-5" /> : <ArrowDownLeft className="w-5 h-5" />}
                        </div>
                        <div>
                          <p className="text-sm font-bold text-gray-900">{payment.service_name || "Service Payment"}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className={cn(
                              "text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-md",
                              payment.status === "released" ? "bg-green-50 text-green-700" : 
                              payment.status === "held" ? "bg-blue-50 text-blue-700" : "bg-gray-50 text-gray-700"
                            )}>
                              {payment.status}
                            </span>
                            <span className="text-[10px] text-gray-400">
                              {new Date(payment.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="text-right flex flex-col items-end gap-1">
                        <div className="font-bold text-gray-900">
                          <Price amount={payment.amount} />
                        </div>
                        {payment.transaction_hash && (
                          <a 
                            href={`https://stellar.expert/explorer/testnet/tx/${payment.transaction_hash}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-blue-600 hover:underline flex items-center gap-1"
                          >
                            TX Hash
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {selectedBooking && (
        <PaymentModal
          booking={selectedBooking}
          isOpen={!!selectedBooking}
          onClose={() => setSelectedBooking(null)}
          onSuccess={() => {
            loadData();
            setSelectedBooking(null);
          }}
        />
      )}
    </div>
  );
}
