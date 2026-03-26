"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { mockDisputes, DisputeItem } from "@/lib/mockDisputes";
import { FairnessReport } from "@/components/dispute/FairnessReport";
import { 
  ArrowLeft, 
  MessageSquare, 
  Image as ImageIcon, 
  FileText, 
  ShieldCheck, 
  Gavel,
  User,
  ExternalLink,
  Loader2
} from "lucide-react";
import Link from "next/link";
import { format } from "date-fns";
import { toast } from "sonner";

export default function DisputeDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [dispute, setDispute] = useState<DisputeItem | null>(null);
  const [isArbitrating, setIsArbitrating] = useState<"client" | "artisan" | null>(null);

  useEffect(() => {
    const found = mockDisputes.find((d) => d.id === id);
    if (found) {
      setDispute(found);
    }
  }, [id]);

  if (!dispute) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
        <p className="text-muted-foreground">Loading case details...</p>
      </div>
    );
  }

  const handleArbitrate = async (winner: "client" | "artisan") => {
    setIsArbitrating(winner);
    
    // Simulate Soroban contract call
    try {
      toast.info(`Initiating arbitration for ${winner === "client" ? dispute.client_name : dispute.artisan_name}...`);
      
      // In a real scenario, we would call the Soroban contract here:
      // await arbitrate(dispute.booking_id, winner === "client" ? clientAddr : artisanAddr);
      
      await new Promise(resolve => setTimeout(resolve, 3000)); // Simulate delay
      
      toast.success("Arbitration successful! Funds distributed on-chain.", {
        description: `Tx Hash: 0x${Math.random().toString(16).slice(2)}...`,
      });
      
      router.push("/dashboard/admin/disputes");
    } catch (err) {
      toast.error("Arbitration failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setIsArbitrating(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <Link 
          href="/dashboard/admin/disputes" 
          className="inline-flex items-center text-sm font-medium text-muted-foreground hover:text-primary transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Disputes
        </Link>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="text-xs font-mono bg-muted px-2 py-0.5 rounded border border-border">#{dispute.id}</span>
              <h1 className="text-3xl font-bold text-foreground">Review Dispute</h1>
            </div>
            <p className="text-muted-foreground">
              Opened on {format(new Date(dispute.created_at), "MMMM d, yyyy 'at' h:mm a")}
            </p>
          </div>
          
          <div className="flex gap-3">
            <button
              onClick={() => handleArbitrate("client")}
              disabled={isArbitrating !== null}
              className="inline-flex items-center px-4 py-2 rounded-lg bg-rose-600 text-white font-bold hover:bg-rose-700 disabled:opacity-50 transition-all shadow-lg active:scale-95"
            >
              {isArbitrating === "client" ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Gavel className="w-4 h-4 mr-2" />}
              Award Client
            </button>
            <button
              onClick={() => handleArbitrate("artisan")}
              disabled={isArbitrating !== null}
              className="inline-flex items-center px-4 py-2 rounded-lg bg-emerald-600 text-white font-bold hover:bg-emerald-700 disabled:opacity-50 transition-all shadow-lg active:scale-95"
            >
              {isArbitrating === "artisan" ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Gavel className="w-4 h-4 mr-2" />}
              Award Artisan
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Evidence */}
        <div className="lg:col-span-2 space-y-8">
          {/* SOW & Context */}
          <section className="bg-card rounded-2xl border border-border overflow-hidden shadow-sm">
            <div className="px-6 py-4 bg-muted/30 border-b border-border flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              <h2 className="font-bold">Project Context (SOW)</h2>
            </div>
            <div className="p-6">
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <p className="text-foreground leading-relaxed">
                  {dispute.evidence.sow_content}
                </p>
              </div>
              <div className="mt-6 pt-6 border-t border-border/50 grid grid-cols-2 gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                    <User className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-[10px] uppercase font-bold text-muted-foreground">Client</p>
                    <p className="text-sm font-semibold">{dispute.client_name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                    <User className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-[10px] uppercase font-bold text-muted-foreground">Artisan</p>
                    <p className="text-sm font-semibold">{dispute.artisan_name}</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Photo Evidence */}
          <section className="bg-card rounded-2xl border border-border overflow-hidden shadow-sm">
            <div className="px-6 py-4 bg-muted/30 border-b border-border flex items-center gap-2">
              <ImageIcon className="w-5 h-5 text-primary" />
              <h2 className="font-bold">Visual Evidence (Before vs After)</h2>
            </div>
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Before Project Start</p>
                <div className="aspect-video relative rounded-xl overflow-hidden border border-border group">
                  <img 
                    src={dispute.evidence.before_photo_url} 
                    alt="Before evidence" 
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <ExternalLink className="w-6 h-6 text-white" />
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground italic">After Claimed Completion</p>
                <div className="aspect-video relative rounded-xl overflow-hidden border border-border group">
                  <img 
                    src={dispute.evidence.after_photo_url} 
                    alt="After evidence" 
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <ExternalLink className="w-6 h-6 text-white" />
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Chat Logs */}
          <section className="bg-card rounded-2xl border border-border overflow-hidden shadow-sm">
            <div className="px-6 py-4 bg-muted/30 border-b border-border flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-primary" />
              <h2 className="font-bold">Communication Logs</h2>
            </div>
            <div className="p-6">
              <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                {dispute.evidence.chat_logs.map((log, idx) => (
                  <div 
                    key={idx} 
                    className={cn(
                      "flex flex-col max-w-[80%] rounded-2xl p-4 text-sm relative",
                      log.role === "client" 
                        ? "bg-muted self-start" 
                        : "bg-primary/10 text-primary-foreground self-end bg-primary/90"
                    )}
                  >
                    <span className={cn(
                      "text-[10px] font-bold uppercase mb-1",
                      log.role === "client" ? "text-muted-foreground" : "text-primary-foreground/70"
                    )}>
                      {log.role === "client" ? dispute.client_name : dispute.artisan_name}
                    </span>
                    <p className={log.role === "artisan" ? "text-white" : "text-foreground"}>
                      {log.message}
                    </p>
                    <span className={cn(
                      "text-[9px] mt-2 block opacity-60 text-right",
                      log.role === "artisan" ? "text-white" : ""
                    )}>
                      {format(new Date(log.timestamp), "HH:mm")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>

        {/* Right Column: Analysis */}
        <div className="space-y-6">
          <FairnessReport score={dispute.fairness_score} />
          
          <div className="bg-card rounded-2xl border border-border p-6 shadow-sm">
            <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
              AI Analysis Score
            </h3>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm">Confidence Score (Issue-23):</span>
              <span className={cn(
                "font-bold",
                dispute.confidence_score >= 0.8 ? "text-emerald-500" : "text-amber-500"
              )}>
                {Math.round(dispute.confidence_score * 100)}%
              </span>
            </div>
            <div className="w-full bg-muted rounded-full h-2">
              <div 
                className={cn(
                  "h-2 rounded-full transition-all duration-1000",
                  dispute.confidence_score >= 0.8 ? "bg-emerald-500" : "bg-amber-500"
                )}
                style={{ width: `${dispute.confidence_score * 100}%` }}
              />
            </div>
            <p className="mt-4 text-xs text-muted-foreground leading-relaxed italic">
              "The high confidence score indicates that objective data (photos, SOW) aligns strongly with the artisan's claim of completion."
            </p>
          </div>

          <div className="bg-amber-50 dark:bg-amber-900/10 rounded-2xl border border-amber-200 dark:border-amber-900/50 p-6">
            <h3 className="font-bold text-amber-800 dark:text-amber-400 mb-2 flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              Arbitrator's Note
            </h3>
            <p className="text-sm text-amber-900/70 dark:text-amber-400/70 leading-relaxed">
              Resolving this dispute will initiate an atomic on-chain transaction. Once the 'arbitrate' function is executed on Soroban, funds will be released immediately and the action cannot be reversed.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
