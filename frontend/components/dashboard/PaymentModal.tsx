"use client";

import { useState } from "react";
import { 
  X, 
  ShieldCheck, 
  Wallet, 
  ArrowRight, 
  Loader2, 
  CheckCircle2,
  AlertCircle,
  ExternalLink
} from "lucide-react";
import { Button } from "../ui/button";
import Price from "../ui/Price";
import { useWallet } from "../../context/WalletContext";
import { useAuth } from "../../context/AuthContext";
import { api } from "../../lib/api";
import { toast } from "sonner";
import { cn } from "../../lib/utils";

interface PaymentModalProps {
  booking: any;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

type PaymentStep = "review" | "prepare" | "sign" | "submit" | "success" | "error";

export default function PaymentModal({ booking, isOpen, onClose, onSuccess }: PaymentModalProps) {
  const { address, connect, isConnected, signTransaction } = useWallet();
  const { token } = useAuth();
  
  const [step, setStep] = useState<PaymentStep>("review");
  const [loading, setLoading] = useState(false);
  const [txHash, setTxHash] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleStartPayment = async () => {
    if (!isConnected) {
      await connect();
      return;
    }
    setStep("prepare");
    setLoading(true);
    
    try {
      // 1. Prepare
      const prepareRes = await api.payments.prepare({
        booking_id: booking.id,
        amount: booking.estimated_cost || 0,
        client_public: address!,
      }, token!);
      
      if (!prepareRes.xdr) throw new Error("Failed to get payment XDR");
      
      // 2. Sign
      setStep("sign");
      const signedXdr = await signTransaction(prepareRes.xdr);
      
      // 3. Submit
      setStep("submit");
      const submitRes = await api.payments.submit({
        signed_xdr: signedXdr
      }, token!);
      
      setTxHash(submitRes.transaction_hash || null);
      setStep("success");
      toast.success("Payment submitted successfully!");
    } catch (err) {
      console.error("Payment failed:", err);
      setErrorMessage(err instanceof Error ? err.message : "Payment failed. Please try again.");
      setStep("error");
    } finally {
      setLoading(false);
    }
  };

  const stepsInfo = {
    review: {
      title: "Review Payment",
      description: "Confirm the details below before funding the escrow.",
      icon: ShieldCheck,
      color: "text-blue-600"
    },
    prepare: {
      title: "Preparing Transaction",
      description: "Getting payment details from the network...",
      icon: Loader2,
      color: "text-blue-600 animate-spin"
    },
    sign: {
      title: "Waiting for Signature",
      description: "Please sign the transaction in your wallet popup.",
      icon: Wallet,
      color: "text-indigo-600"
    },
    submit: {
      title: "Submitting to Network",
      description: "Finalizing your payment on the Stellar blockchain...",
      icon: Loader2,
      color: "text-green-600 animate-spin"
    },
    success: {
      title: "Payment Successful",
      description: "Funds are now securely held in escrow.",
      icon: CheckCircle2,
      color: "text-green-600"
    },
    error: {
      title: "Payment Failed",
      description: errorMessage || "Something went wrong during the payment process.",
      icon: AlertCircle,
      color: "text-red-600"
    }
  };

  const currentStep = stepsInfo[step];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm transition-opacity">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className={cn("p-2 rounded-xl bg-gray-50", currentStep.color)}>
                <currentStep.icon className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">{currentStep.title}</h2>
                <p className="text-sm text-gray-500">{currentStep.description}</p>
              </div>
            </div>
            {step !== "prepare" && step !== "sign" && step !== "submit" && (
              <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
                <X className="w-6 h-6" />
              </button>
            )}
          </div>

          {(step === "review" || step === "prepare" || step === "sign" || step === "submit") && (
            <div className="bg-gray-50 rounded-2xl p-5 mb-6 space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Service</span>
                <span className="text-sm font-semibold text-gray-900">{booking.service}</span>
              </div>
              <div className="flex justify-between items-center border-t border-gray-100 pt-3">
                <span className="text-sm text-gray-500">Artisan</span>
                <span className="text-sm font-semibold text-gray-900">{booking.artisan_name}</span>
              </div>
              <div className="flex justify-between items-center border-t border-gray-100 pt-3">
                <span className="text-sm text-gray-500">Amount to Fund</span>
                <div className="text-lg font-bold text-blue-600">
                  <Price amount={booking.estimated_cost || 0} />
                </div>
              </div>
            </div>
          )}

          {step === "success" && (
            <div className="text-center py-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 bg-green-50 text-green-700 rounded-full text-xs font-bold mb-6">
                <ShieldCheck className="w-3.5 h-3.5" />
                SECURED BY STELLAR ESCROW
              </div>
              
              {txHash && (
                <a 
                  href={`https://stellar.expert/explorer/testnet/tx/${txHash}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 text-sm text-blue-600 hover:underline mb-8"
                >
                  View on Stellar Explorer
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}

              <Button 
                className="w-full bg-gray-900 hover:bg-black text-white py-6 rounded-2xl"
                onClick={() => {
                  onSuccess();
                  onClose();
                }}
              >
                Return to Dashboard
              </Button>
            </div>
          )}

          {step === "error" && (
            <div className="space-y-4">
              <Button 
                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-6 rounded-2xl"
                onClick={() => setStep("review")}
              >
                Try Again
              </Button>
              <Button 
                variant="ghost" 
                className="w-full text-gray-500"
                onClick={onClose}
              >
                Cancel
              </Button>
            </div>
          )}

          {step === "review" && (
            <div className="space-y-4">
              {!isConnected ? (
                <Button 
                  className="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-6 rounded-2xl flex items-center justify-center gap-2"
                  onClick={connect}
                >
                  <Wallet className="w-5 h-5" />
                  Connect Wallet
                </Button>
              ) : (
                <Button 
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white py-6 rounded-2xl flex items-center justify-center gap-2 shadow-lg shadow-blue-200"
                  onClick={handleStartPayment}
                  disabled={loading}
                >
                  {loading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      Confirm & Pay
                      <ArrowRight className="w-5 h-5" />
                    </>
                  )}
                </Button>
              )}
              <p className="text-[10px] text-center text-gray-400 uppercase tracking-widest font-bold">
                Funds will be locked in escrow until you approve the work.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
