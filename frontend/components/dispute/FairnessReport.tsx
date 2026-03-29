"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface FairnessReportProps {
  score: number; // 0.0 to 1.0
  className?: string;
}

export function FairnessReport({ score, className }: FairnessReportProps) {
  const percentage = Math.round(score * 100);
  
  // Color based on score
  const getColor = (s: number) => {
    if (s >= 0.8) return "text-emerald-500 stroke-emerald-500";
    if (s >= 0.5) return "text-amber-500 stroke-amber-500";
    return "text-rose-500 stroke-rose-500";
  };

  const colorClasses = getColor(score);
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score * circumference);

  return (
    <div className={cn("flex flex-col items-center justify-center p-6 bg-secondary/30 rounded-2xl border border-border/50 backdrop-blur-sm", className)}>
      <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">Fairness Score</h3>
      
      <div className="relative flex items-center justify-center">
        {/* Shadow Ring */}
        <svg className="w-32 h-32 transform -rotate-90">
          <circle
            cx="64"
            cy="64"
            r={radius}
            stroke="currentColor"
            strokeWidth="8"
            fill="transparent"
            className="text-muted/20"
          />
          {/* Progress Ring */}
          <circle
            cx="64"
            cy="64"
            r={radius}
            stroke="currentColor"
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            fill="transparent"
            className={cn("transition-all duration-1000 ease-out", colorClasses.split(' ')[1])}
          />
        </svg>
        
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn("text-3xl font-bold font-mono tracking-tighter", colorClasses.split(' ')[0])}>
            {percentage}%
          </span>
        </div>
      </div>
      
      <div className="mt-4 text-center">
        <p className="text-sm text-muted-foreground">
          {score >= 0.8 ? "Highly Objective" : score >= 0.5 ? "Sufficient Context" : "Subjective / Missing Info"}
        </p>
      </div>
    </div>
  );
}
