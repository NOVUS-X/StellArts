"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../../components/ui/dialog";
import { api, type BookingResponse } from "../../../lib/api";
import { useAuth } from "../../../context/AuthContext";
import { useWallet } from "../../../context/WalletContext";
import { Wallet, CheckCircle2, AlertCircle, History, ExternalLink, Loader2, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export default function DashboardPaymentsPage() {
  const { token, isAuthenticated, isLoading } = useAuth();
  const { isConnected, address, connect, signTransaction } = useWallet();
  const [paymentsRequired, setPaymentsRequired] = useState<BookingResponse[]>([]);
  const [paymentHistory, setPaymentHistory] = useState<BookingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Payment Processing State
  const [selectedBooking, setSelectedBooking] = useState<BookingResponse | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetchBookings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const fetchBookings = () => {
    if (!token) return;
    setLoading(true);
    api.bookings
      .myBookings(token)
      .then((data) => {
        // Bookings that need funding: Confirmed status and client needs to pay in escrow
        setPaymentsRequired(data.filter(b => b.status === "confirmed"));
        // Payment history: Bookings that are funded/paid or in progress
        setPaymentHistory(data.filter(b => ["in_progress", "completed"].includes(b.status)));
      })
      .catch((err) => {
        console.error("Failed to load bookings for payments", err);
        toast.error("Failed to load payment information");
      })
      .finally(() => setLoading(false));
  };

  const handlePay = async () => {
    if (!selectedBooking || !token) return;
    if (!isConnected || !address) {
      toast.error("Please connect your wallet first");
      return;
    }

    setIsProcessing(true);
    try {
      toast.info("Preparing transaction...");
      const { xdr } = await api.payments.prepare(
        selectedBooking.id, 
        selectedBooking.estimated_cost || 0,
        token
      );

      toast.info("Please sign the transaction in your wallet...");
      const signedXdr = await signTransaction(xdr);

      toast.info("Submitting transaction to network...");
      const result = await api.payments.submit(selectedBooking.id, signedXdr, token);

      if (result.success) {
        toast.success(
          <div className="flex flex-col gap-1">
            <span>Payment successfully locked in escrow!</span>
            <a 
              href={`https://stellar.expert/explorer/testnet/tx/${result.hash}`} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-xs underline flex items-center gap-1"
            >
              View on Explorer <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        );
        setSelectedBooking(null);
        // Refresh bookings and also optimistic update
        setPaymentsRequired(prev => prev.filter(b => b.id !== selectedBooking.id));
        setPaymentHistory(prev => [selectedBooking, ...prev]);
        
        // Wait then refetch for sure
        setTimeout(fetchBookings, 2000);
      }
    } catch (err) {
      console.error(err);
      toast.error(err instanceof Error ? err.message : "Payment failed. Please try again.");
    } finally {
      setIsProcessing(false);
    }
  };

  if (!isAuthenticated && !isLoading) return null;

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-12 border-b border-gray-100 pb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 mb-2">Payments</h1>
          <p className="text-slate-500 text-base max-w-2xl">Fund your escrows securely, manage upcoming payments, and view your complete transaction history on the Stellar network.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-10 xl:gap-14">
        <div className="lg:col-span-2 space-y-6">
          <Card className="rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <CardHeader className="border-b border-gray-50 pb-4">
              <CardTitle className="text-lg flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-amber-500" />
                Payments Required
              </CardTitle>
              <CardDescription>
                Confirmed bookings that need escrow funding before work starts
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-4">
              {loading ? (
                <div className="py-8 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>
              ) : paymentsRequired.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-sm">
                  You have no pending payments.
                </div>
              ) : (
                <div className="space-y-4">
                  {paymentsRequired.map(booking => (
                    <div key={booking.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-6 bg-amber-50/50 rounded-xl border border-amber-100 hover:bg-amber-50 transition-colors">
                      <div>
                        <h4 className="font-semibold text-amber-900 text-lg mb-1">{booking.service}</h4>
                        <p className="text-amber-700 font-medium font-mono">
                          Cost: ${Number(booking.estimated_cost).toFixed(2)}
                        </p>
                      </div>
                      <button
                        onClick={() => setSelectedBooking(booking)}
                        className="mt-3 sm:mt-0 flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
                      >
                       Pay Now <ArrowRight className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <CardHeader className="border-b border-gray-50 pb-4">
              <CardTitle className="text-lg flex items-center gap-2">
                <History className="w-5 h-5 text-gray-500" />
                Payment History
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              {loading ? (
                 <div className="py-8 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>
              ) : paymentHistory.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-sm">
                  No payment history found. Once you fund an escrow, it will appear here.
                </div>
              ) : (
                <div className="space-y-3">
                  {paymentHistory.map(booking => (
                    <div key={booking.id} className="flex items-center justify-between p-4 hover:bg-slate-50 rounded-xl border border-transparent hover:border-slate-100 transition-all">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                          <CheckCircle2 className="w-5 h-5 text-green-600" />
                        </div>
                        <div>
                          <h4 className="font-medium text-gray-900 text-sm">{booking.service}</h4>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {new Date(booking.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-gray-900">${Number(booking.estimated_cost).toFixed(2)}</p>
                        <p className="text-xs text-green-600 font-medium">{booking.status === "completed" ? "Released" : "In Escrow"}</p>
                      </div>
                      {/* For a real app, we'd save the Tx Hash in DB and display it here */}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Wallet Widget */}
        <div className="space-y-6">
          <Card className={`rounded-2xl shadow-sm overflow-hidden border ${isConnected ? 'border-emerald-200 bg-emerald-50/30' : 'border-gray-200 bg-slate-50/50'}`}>
            <CardHeader className="pb-4 border-b border-gray-100 bg-white/50">
              <CardTitle className="text-xl font-bold flex items-center gap-3">
                <Wallet className={`w-6 h-6 ${isConnected ? 'text-emerald-600' : 'text-blue-600'}`} />
                Stellar Wallet
              </CardTitle>
              <CardDescription className="text-base mt-2">
                {isConnected ? 'Your wallet is connected and ready to sign transactions on the Stellar network.' : 'Connect your wallet to fund your escrow agreements and release payments seamlessly.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {isConnected && address ? (
                <div className="space-y-4">
                  <div className="p-4 bg-white rounded-xl border border-emerald-100 shadow-sm">
                    <p className="text-sm text-emerald-600 uppercase tracking-widest font-bold mb-2">Connected Address</p>
                    <p className="text-base font-mono text-slate-900 truncate bg-slate-50 px-3 py-2 rounded-lg">
                      {address.slice(0, 10)}…{address.slice(-10)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-emerald-800 bg-emerald-100/50 px-4 py-3 rounded-xl font-semibold border border-emerald-200">
                     <CheckCircle2 className="w-5 h-5 text-emerald-600" /> Connected to Testnet
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={connect}
                  className="w-full rounded-xl bg-blue-600 px-6 py-4 text-white font-bold text-lg hover:bg-blue-700 hover:shadow-md hover:shadow-blue-600/20 transition-all flex justify-center items-center gap-3"
                >
                  <Wallet className="w-6 h-6" /> Connect Wallet
                </button>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Payment Modal */}
      <Dialog open={!!selectedBooking} onOpenChange={(open: boolean) => !open && !isProcessing && setSelectedBooking(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Fund Escrow</DialogTitle>
            <DialogDescription>
              You are about to lock funds in the StellArts escrow smart contract for this service.
            </DialogDescription>
          </DialogHeader>
          
          {selectedBooking && (
            <div className="py-4 space-y-4">
               <div className="bg-gray-50 p-4 rounded-lg flex justify-between items-center border border-gray-200">
                 <div>
                   <p className="text-sm font-medium text-gray-900">{selectedBooking.service}</p>
                   <p className="text-xs text-gray-500">Artisan SRV-{selectedBooking.artisan_id}</p>
                 </div>
                 <div className="text-right">
                   <p className="text-2xl font-bold text-gray-900">${Number(selectedBooking.estimated_cost).toFixed(2)}</p>
                   <p className="text-xs text-gray-500">USDC (Testnet)</p>
                 </div>
               </div>
               
               <div className="bg-blue-50 text-blue-800 p-3 rounded-lg text-sm flex gap-2">
                 <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0" />
                 <p>Funds will be held securely in escrow and released only when the job is marked as completed.</p>
               </div>
            </div>
          )}

          <DialogFooter className="sm:justify-end gap-2">
             <button
                type="button"
                onClick={() => setSelectedBooking(null)}
                disabled={isProcessing}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition disabled:opacity-50"
             >
               Cancel
             </button>
             <button
                type="button"
                onClick={handlePay}
                disabled={isProcessing || !isConnected}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition disabled:opacity-70 flex items-center justify-center min-w-[120px]"
             >
               {isProcessing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
               {isProcessing ? "Processing..." : "Sign & Submit"}
             </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
