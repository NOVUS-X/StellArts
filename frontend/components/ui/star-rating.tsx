"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

interface StarRatingProps {
  rating: number;
  onRatingChange?: (rating: number) => void;
  size?: "sm" | "md" | "lg";
  readonly?: boolean;
}

export default function StarRating({
  rating,
  onRatingChange,
  size = "md",
  readonly = false,
}: StarRatingProps) {
  const [hoverRating, setHoverRating] = useState(0);

  const sizeClasses = {
    sm: "w-4 h-4",
    md: "w-6 h-6",
    lg: "w-8 h-8",
  };

  const handleMouseEnter = (starIndex: number) => {
    if (!readonly) {
      setHoverRating(starIndex);
    }
  };

  const handleMouseLeave = () => {
    if (!readonly) {
      setHoverRating(0);
    }
  };

  const handleClick = (starIndex: number) => {
    if (!readonly && onRatingChange) {
      onRatingChange(starIndex);
    }
  };

  return (
    <div className="flex gap-1" onMouseLeave={handleMouseLeave}>
      {[1, 2, 3, 4, 5].map((starIndex) => {
        const displayRating = hoverRating || rating;
        const isFilled = starIndex <= displayRating;

        return (
          <button
            key={starIndex}
            type="button"
            disabled={readonly}
            className={cn(
              "transition-all duration-200",
              !readonly && "cursor-pointer hover:scale-110",
              readonly && "cursor-default",
              isFilled ? "text-yellow-400" : "text-gray-300",
            )}
            onMouseEnter={() => handleMouseEnter(starIndex)}
            onClick={() => handleClick(starIndex)}
            aria-label={`Rate ${starIndex} star${starIndex > 1 ? "s" : ""}`}
          >
            <Star
              className={cn(
                sizeClasses[size],
                isFilled ? "fill-current" : "fill-none",
              )}
            />
          </button>
        );
      })}
    </div>
  );
}
