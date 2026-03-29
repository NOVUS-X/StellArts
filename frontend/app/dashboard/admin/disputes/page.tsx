"use client";

import React, { useState } from "react";
import Link from "next/link";
import { mockDisputes, DisputeItem } from "@/lib/mockDisputes";
import { FairnessReport } from "@/components/dispute/FairnessReport";
import { 
  AlertCircle, 
  ChevronRight, 
  Search, 
  Filter, 
  CheckCircle2, 
  Clock, 
  Scale 
} from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";

export default function AdminDisputesPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filteredDisputes = mockDisputes.filter((d) => {
    const matchesSearch = 
      d.client_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.artisan_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.id.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === "all" || d.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
            <Clock className="w-3 h-3 mr-1" />
            Pending Action
          </span>
        );
      case "resolved_client":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">
            <CheckCircle2 className="w-3 h-3 mr-1" />
            Resolved (Client)
          </span>
        );
      case "resolved_artisan":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
            <CheckCircle2 className="w-3 h-3 mr-1" />
            Resolved (Artisan)
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-extrabold text-foreground flex items-center">
            <Scale className="w-8 h-8 mr-3 text-primary" />
            Arbitration Center
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Review and resolve on-chain disputes between clients and artisans.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="md:col-span-2 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by ID, Client or Artisan..."
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all outline-none"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <select
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background appearance-none focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="resolved_client">Resolved (Client)</option>
            <option value="resolved_artisan">Resolved (Artisan)</option>
          </select>
        </div>
      </div>

      {/* Dispute List */}
      <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-muted/50 border-b border-border">
              <tr>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">ID</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Parties</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Amount</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Fairness</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Status</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {filteredDisputes.length > 0 ? (
                filteredDisputes.map((dispute) => (
                  <tr key={dispute.id} className="hover:bg-muted/20 transition-colors group">
                    <td className="px-6 py-4 font-mono text-sm text-muted-foreground">{dispute.id}</td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-semibold text-foreground">{dispute.client_name}</span>
                        <span className="text-xs text-muted-foreground italic">vs</span>
                        <span className="font-semibold text-foreground">{dispute.artisan_name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-bold text-foreground">{dispute.amount} XLM</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className={cn(
                          "w-2 h-2 rounded-full",
                          dispute.fairness_score >= 0.8 ? "bg-emerald-500" : 
                          dispute.fairness_score >= 0.5 ? "bg-amber-500" : "bg-rose-500"
                        )} />
                        <span className="text-sm font-medium">{Math.round(dispute.fairness_score * 100)}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">{getStatusBadge(dispute.status)}</td>
                    <td className="px-6 py-4 text-right">
                      <Link 
                        href={`/dashboard/admin/disputes/${dispute.id}`}
                        className="inline-flex items-center justify-center p-2 rounded-lg bg-primary/10 text-primary hover:bg-primary hover:text-white transition-all group-hover:px-4"
                      >
                        <span className="sr-only sm:not-sr-only sm:mr-2 text-sm font-bold opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap overflow-hidden">
                          Review Case
                        </span>
                        <ChevronRight className="w-4 h-4" />
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center">
                    <div className="flex flex-col items-center">
                      <AlertCircle className="w-12 h-12 text-muted-foreground mb-4 opacity-20" />
                      <p className="text-muted-foreground font-medium">No disputes found matching your criteria.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="px-6 py-4 bg-muted/30 border-t border-border flex justify-between items-center text-xs text-muted-foreground">
          <span>Showing {filteredDisputes.length} disputes</span>
          <span>Last automated update: {format(new Date(), "HH:mm:ss")}</span>
        </div>
      </div>
    </div>
  );
}
