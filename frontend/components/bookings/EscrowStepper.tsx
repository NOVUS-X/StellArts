"use client";

import { useState } from "react";
import { 
  CheckCircle2, 
  Circle, 
  CreditCard, 
  Lock, 
  PackageCheck, 
  ShieldAlert, 
  Loader2,
  AlertCircle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export type EscrowStatus = "HELD" | "FUNDED" | "RELEASED" | "DISPUTED";

interface EscrowStepperProps {
  bookingId: string;
  initialStatus: EscrowStatus;
  serviceName: string;
  amount?: number;
}

export default function EscrowStepper({ 
  bookingId, 
  initialStatus, 
  serviceName,
  amount 
}: EscrowStepperProps) {
  const [status, setStatus] = useState<EscrowStatus>(initialStatus);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const steps = [
    { 
      id: "HELD", 
      label: "Pending Payment", 
      icon: CreditCard,
      description: "Payment requested by artisan" 
    },
    { 
      id: "FUNDED", 
      label: "Funds in Escrow", 
      icon: Lock,
      description: "Funds securely held in contract" 
    },
    { 
      id: "RELEASED", 
      label: "Payment Released", 
      icon: PackageCheck,
      description: "Artisan has been paid" 
    }
  ];

  const currentStepIndex = steps.findIndex(s => s.id === status);
  const isDisputed = status === "DISPUTED";

  const handleAction = async (action: "pay" | "release" | "dispute") => {
    setLoadingAction(action);
    
    // Simulate blockchain delay
    await new Promise(resolve => setTimeout(resolve, 2000));

    try {
      if (action === "pay") {
        setStatus("FUNDED");
        toast.success("Payment successful! Funds are now in escrow.");
      } else if (action === "release") {
        setStatus("RELEASED");
        toast.success("Funds released to the artisan.");
      } else if (action === "dispute") {
        setStatus("DISPUTED");
        toast.error("Dispute initiated. Our team will review the case.");
      }
    } catch (error) {
      toast.error("Transaction failed. Please try again.");
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="mt-6 border rounded-xl overflow-hidden bg-white shadow-sm border-gray-100">
      <div className="bg-gray-50/50 px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-blue-600" />
          Escrow Security: {serviceName}
        </h4>
        <span className={cn(
          "text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider",
          status === "HELD" && "bg-amber-100 text-amber-700",
          status === "FUNDED" && "bg-blue-100 text-blue-700",
          status === "RELEASED" && "bg-green-100 text-green-700",
          status === "DISPUTED" && "bg-red-100 text-red-700"
        )}>
          {status}
        </span>
      </div>

      <div className="p-6">
        {/* Stepper Visual */}
        <div className="relative flex justify-between items-start mb-8">
          {/* Connector Line */}
          <div className="absolute top-5 left-0 w-full h-0.5 bg-gray-100 -z-0">
            <div 
              className="h-full bg-blue-600 transition-all duration-500 ease-in-out" 
              style={{ width: `${(Math.max(0, currentStepIndex) / (steps.length - 1)) * 100}%` }}
            />
          </div>

          {steps.map((step, index) => {
            const Icon = step.icon;
            const isCompleted = index < currentStepIndex || status === "RELEASED";
            const isActive = index === currentStepIndex && !isDisputed;
            
            return (
              <div key={step.id} className="relative z-10 flex flex-col items-center w-1/3">
                <div className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300",
                  isCompleted ? "bg-blue-600 text-white shadow-blue-200 shadow-lg" : 
                  isActive ? "bg-white border-2 border-blue-600 text-blue-600 shadow-md scale-110" : 
                  "bg-white border-2 border-gray-200 text-gray-400"
                )}>
                  {isCompleted ? <CheckCircle2 className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
                </div>
                <div className="mt-3 text-center">
                  <p className={cn(
                    "text-xs font-bold",
                    isActive ? "text-blue-700" : isCompleted ? "text-gray-900" : "text-gray-400"
                  )}>
                    {step.label}
                  </p>
                  <p className="text-[10px] text-gray-400 mt-1 hidden sm:block">
                    {step.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Dispute State Banner */}
        {isDisputed && (
          <div className="mb-6 p-4 bg-red-50 border border-red-100 rounded-lg flex gap-3 text-red-700">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <div>
              <p className="text-sm font-bold">Booking Disputed</p>
              <p className="text-xs mt-1">Funds are locked until a resolution is reached.</p>
            </div>
          </div>
        )}

        {/* Actions Section */}
        <div className="flex flex-wrap gap-3 justify-end items-center">
          {status === "HELD" && (
            <Button 
              size="sm"
              onClick={() => handleAction("pay")}
              disabled={!!loadingAction}
              className="bg-blue-600 hover:bg-blue-700 text-white min-w-[100px]"
            >
              {loadingAction === "pay" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Paying...
                </>
              ) : (
                "Pay Now"
              )}
            </Button>
          )}

          {status === "FUNDED" && (
            <>
              <Button 
                variant="outline"
                size="sm"
                onClick={() => handleAction("dispute")}
                disabled={!!loadingAction}
                className="text-red-600 border-red-200 hover:bg-red-50"
              >
                {loadingAction === "dispute" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Initiate Dispute"
                )}
              </Button>
              <Button 
                size="sm"
                onClick={() => handleAction("release")}
                disabled={!!loadingAction}
                className="bg-green-600 hover:bg-green-700 text-white"
              >
                {loadingAction === "release" ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Releasing...
                  </>
                ) : (
                  "Release Funds"
                )}
              </Button>
            </>
          )}

          {status === "RELEASED" && (
            <p className="text-sm text-green-600 font-medium flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              Transaction Complete
            </p>
          )}

          {status === "DISPUTED" && (
            <Button 
              variant="link"
              size="sm"
              className="text-blue-600 p-0 h-auto font-bold"
            >
              View Support Ticket
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
