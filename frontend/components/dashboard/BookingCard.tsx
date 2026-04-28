"use client";

import { useState } from "react";
import { 
  Calendar, 
  MapPin, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  PlayCircle,
  MoreVertical,
  ExternalLink
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import Price from "../ui/Price";
import { cn } from "../../lib/utils";
import type { BookingResponse } from "../../lib/api";
import { api } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";
import { toast } from "sonner";

interface BookingCardProps {
  booking: BookingResponse;
  onStatusUpdate: (updatedBooking: BookingResponse) => void;
  onPayNow?: (booking: BookingResponse) => void;
}

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: any }> = {
  pending: { bg: "bg-amber-100", text: "text-amber-700", icon: Clock },
  confirmed: { bg: "bg-blue-100", text: "text-blue-700", icon: CheckCircle2 },
  in_progress: { bg: "bg-indigo-100", text: "text-indigo-700", icon: PlayCircle },
  completed: { bg: "bg-green-100", text: "text-green-700", icon: CheckCircle2 },
  cancelled: { bg: "bg-gray-100", text: "text-gray-700", icon: XCircle },
  disputed: { bg: "bg-red-100", text: "text-red-700", icon: XCircle },
};

export default function BookingCard({ booking, onStatusUpdate, onPayNow }: BookingCardProps) {
  const { user, token } = useAuth();
  const [loading, setLoading] = useState(false);

  const statusInfo = STATUS_STYLES[booking.status] || STATUS_STYLES.pending;
  const StatusIcon = statusInfo.icon;

  const isClient = user?.role === "client";
  const isArtisan = user?.role === "artisan";

  const handleUpdateStatus = async (newStatus: string) => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await api.bookings.updateStatus(booking.id, newStatus, token);
      toast.success(res.message);
      onStatusUpdate({ ...booking, status: newStatus });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="overflow-hidden border-gray-200 hover:border-blue-300 transition-all duration-200 shadow-sm hover:shadow-md">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 bg-gray-50/50">
        <div className="flex flex-col gap-1">
          <CardTitle className="text-lg font-bold text-gray-900">
            {booking.service}
          </CardTitle>
          <p className="text-xs text-gray-500 font-mono uppercase">ID: {booking.id.slice(0, 8)}...</p>
        </div>
        <div className={cn(
          "flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider",
          statusInfo.bg,
          statusInfo.text
        )}>
          <StatusIcon className="w-3.5 h-3.5" />
          {booking.status}
        </div>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Calendar className="w-4 h-4 text-gray-400" />
              {booking.date ? new Date(booking.date).toLocaleString() : "TBD"}
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <MapPin className="w-4 h-4 text-gray-400" />
              {booking.location || "Online / TBD"}
            </div>
          </div>
          <div className="space-y-2 text-right md:text-right">
            <p className="text-xs text-gray-500 font-medium">Estimated Cost</p>
            <div className="text-xl font-bold text-blue-600">
              <Price amount={booking.estimated_cost || 0} />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-600">
              {(isClient ? booking.artisan_name : booking.client_name)?.[0] || "?"}
            </div>
            <div>
              <p className="text-xs text-gray-500 font-medium">{isClient ? "Artisan" : "Client"}</p>
              <p className="text-sm font-semibold text-gray-900">
                {isClient ? booking.artisan_name : booking.client_name || "Unknown"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Role-specific Actions */}
            {isClient && (
              <>
                {booking.status === "pending" && (
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="text-red-600 border-red-200 hover:bg-red-50"
                    onClick={() => handleUpdateStatus("cancelled")}
                    disabled={loading}
                  >
                    Cancel
                  </Button>
                )}
                {booking.status === "confirmed" && onPayNow && (
                  <Button 
                    size="sm" 
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                    onClick={() => onPayNow(booking)}
                    disabled={loading}
                  >
                    Pay Now
                  </Button>
                )}
                {booking.status === "in_progress" && (
                  <Button 
                    size="sm" 
                    className="bg-green-600 hover:bg-green-700 text-white"
                    onClick={() => handleUpdateStatus("completed")}
                    disabled={loading}
                  >
                    Mark Complete
                  </Button>
                )}
              </>
            )}

            {isArtisan && (
              <>
                {booking.status === "pending" && (
                  <Button 
                    size="sm" 
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                    onClick={() => handleUpdateStatus("confirmed")}
                    disabled={loading}
                  >
                    Confirm
                  </Button>
                )}
                {booking.status === "confirmed" && (
                  <Button 
                    size="sm" 
                    className="bg-indigo-600 hover:bg-indigo-700 text-white"
                    onClick={() => handleUpdateStatus("in_progress")}
                    disabled={loading}
                  >
                    Start Job
                  </Button>
                )}
                {(booking.status === "pending" || booking.status === "confirmed" || booking.status === "in_progress") && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="text-gray-500 hover:text-red-600"
                    onClick={() => handleUpdateStatus("cancelled")}
                    disabled={loading}
                  >
                    Cancel
                  </Button>
                )}
              </>
            )}

            <Button variant="ghost" size="icon" className="text-gray-400">
              <MoreVertical className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
