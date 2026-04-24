"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import StarRating from "@/components/ui/star-rating";
import { Loader2, Star } from "lucide-react";
import { toast } from "sonner";

interface ReviewFormProps {
  bookingId: string;
  artisanId: number;
  artisanName: string;
  onSuccess?: () => void;
}

export default function ReviewForm({
  bookingId,
  artisanId,
  artisanName,
  onSuccess,
}: ReviewFormProps) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (rating === 0) {
      toast.error("Please select a rating");
      return;
    }

    setSubmitting(true);

    try {
      const response = await fetch("/api/v1/reviews/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          booking_id: bookingId,
          artisan_id: artisanId,
          rating,
          comment: comment.trim() || undefined,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to submit review");
      }

      toast.success("Thank you! Your review has been submitted.");

      // Reset form
      setRating(0);
      setComment("");

      // Call success callback if provided
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      console.error("Review submission error:", error);
      toast.error(
        error instanceof Error ? error.message : "Failed to submit review",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const ratingLabels = {
    0: "Select a rating",
    1: "Poor",
    2: "Fair",
    3: "Good",
    4: "Very Good",
    5: "Excellent",
  };

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-6 mt-4">
      <div className="flex items-center gap-2 mb-4">
        <Star className="w-5 h-5 text-blue-600 fill-current" />
        <h3 className="text-lg font-bold text-gray-900">
          Rate Your Experience
        </h3>
      </div>

      <p className="text-sm text-gray-600 mb-4">
        How was your experience with{" "}
        <span className="font-semibold">{artisanName}</span>? Your review helps
        others find quality artisans.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Star Rating */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Rating
          </label>
          <div className="flex items-center gap-3">
            <StarRating rating={rating} onRatingChange={setRating} size="lg" />
            {rating > 0 && (
              <span className="text-sm font-medium text-blue-600">
                {ratingLabels[rating as keyof typeof ratingLabels]}
              </span>
            )}
          </div>
        </div>

        {/* Comment Textarea */}
        <div>
          <label
            htmlFor="review-comment"
            className="block text-sm font-semibold text-gray-700 mb-2"
          >
            Your Review (Optional)
          </label>
          <textarea
            id="review-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Share details of your experience with this artisan..."
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none text-sm"
            maxLength={500}
          />
          <p className="text-xs text-gray-500 mt-1 text-right">
            {comment.length}/500 characters
          </p>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={submitting || rating === 0}
            className="bg-blue-600 hover:bg-blue-700 text-white min-w-[140px]"
          >
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Submitting...
              </>
            ) : (
              "Submit Review"
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
