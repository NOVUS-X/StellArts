"use client";

import { useState } from "react";
import { CheckCircle2, ShieldCheck, Loader2, ExternalLink, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { useWallet } from "@/context/WalletContext";
import { prepareRelease, submitTransaction } from "@/lib/soroban";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

interface ReleaseFundsModalProps {
  isOpen: boolean;
  onClose: () => void;
  bookingId: string;
  amount: number;
  artisanName: string;
  onSuccess: () => void;
}

export default function ReleaseFundsModal({
  isOpen,
  onClose,
  bookingId,
  amount,
  artisanName,
  onSuccess
}: ReleaseFundsModalProps) {
  const { address, isConnected, connect, signTransaction } = useWallet();
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [txHash, setTxHash] = useState<string | null>(null);

  if (!isOpen) return null;

  // Mock logic to derive engagement_id from bookingId UUID (aligned with backend)
  const getEngagementId = (uuid: string) => {
    try {
      const hex = uuid.replace(/-/g, "");
      const bigId = BigInt("0x" + hex);
      return Number((bigId >> BigInt(64)) % BigInt(1000000));
    } catch (e) {
      return 0;
    }
  };

  const handleRelease = async () => {
    if (!isConnected) {
      await connect();
      return;
    }

    if (!token) {
      toast.error("You must be logged in to release funds");
      return;
    }

    setLoading(true);
    try {
      const engagementId = getEngagementId(bookingId);
      
      // 1. Prepare Soroban transaction
      toast.info("Preparing on-chain release...");
      const unsignedXdr = await prepareRelease(address!, engagementId);
      
      // 2. Sign with Wallet
      toast.info("Please sign the transaction in your wallet");
      const signedXdr = await signTransaction(unsignedXdr);
      
      // 3. Submit to Soroban RPC
      toast.info("Submitting to network...");
      const response = await submitTransaction(signedXdr);
      
      setTxHash(response.hash);
      
      // 4. Update backend status
      try {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/bookings/${bookingId}/status`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          },
          body: JSON.stringify({ status: "completed" })
        });
      } catch (e) {
        console.error("Backend status update failed, but on-chain release succeeded", e);
      }
      
      toast.success("Funds released successfully!");
      onSuccess();
    } catch (err: any) {
      console.error(err);
      toast.error(err.message || "Failed to release funds");
    } finally {
      setLoading(false);
    }
  };

  const explorerLink = txHash ? `https://stellar.expert/explorer/testnet/tx/${txHash}` : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <Card className="w-full max-w-md bg-white overflow-hidden shadow-2xl border-none">
        <CardHeader className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white pb-8 relative">
          <button 
            onClick={onClose} 
            className="absolute top-4 right-4 text-white/60 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="p-2 bg-white/20 w-fit rounded-lg mb-4">
            <ShieldCheck className="w-6 h-6 text-white" />
          </div>
          <CardTitle className="text-2xl font-bold">Release Funds</CardTitle>
          <CardDescription className="text-blue-100">
            Authorize the final payment for {artisanName}.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-6 -mt-4 bg-white rounded-t-2xl relative">
          {!txHash ? (
            <div className="space-y-6">
              <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Amount to Release</span>
                  <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Network</span>
                </div>
                <div className="flex justify-between items-end">
                  <span className="text-2xl font-black text-gray-900">{amount.toFixed(2)} <span className="text-sm font-normal text-gray-400">XLM</span></span>
                  <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">TESTNET</span>
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm text-gray-600 leading-relaxed">
                  By confirming, you authorize the smart contract to disburse the held funds. This ensures the artisan is paid for their work.
                </p>
                <div className="flex items-start gap-2 text-[11px] text-amber-700 bg-amber-50 p-3 rounded-lg border border-amber-100">
                  <ExternalLink className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>This action requires a signature from your connected wallet and will incur a small network fee.</span>
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <Button 
                  variant="ghost" 
                  onClick={onClose}
                  className="flex-1 rounded-xl text-gray-500 hover:bg-gray-50"
                  disabled={loading}
                >
                  Cancel
                </Button>
                <Button 
                  onClick={handleRelease}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-lg shadow-blue-200"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Releasing...
                    </>
                  ) : (
                    isConnected ? "Confirm Release" : "Connect Wallet"
                  )}
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-center py-6 space-y-4">
              <div className="w-20 h-20 bg-green-50 text-green-600 rounded-full flex items-center justify-center mx-auto mb-2">
                <CheckCircle2 className="w-12 h-12" />
              </div>
              <div>
                <h3 className="text-2xl font-bold text-gray-900">Payment Released</h3>
                <p className="text-sm text-gray-500 mt-1 px-4">
                  The funds have been successfully transferred to {artisanName}.
                </p>
              </div>
              
              {explorerLink && (
                <div className="pt-2">
                  <a 
                    href={explorerLink} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="inline-flex items-center text-xs font-semibold text-blue-600 hover:text-blue-700 bg-blue-50 px-3 py-1.5 rounded-full transition-colors gap-1.5"
                  >
                    View on Ledger <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}
              
              <div className="pt-4">
                <Button 
                  onClick={onClose}
                  className="w-full bg-gray-900 hover:bg-black text-white rounded-xl py-6"
                >
                  Return to Bookings
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
