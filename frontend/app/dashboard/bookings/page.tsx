"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { api, type BookingResponse } from "../../../lib/api";
import { useAuth } from "../../../context/AuthContext";
import { Calendar, User, Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function DashboardBookingsPage() {
  const { token, user, isAuthenticated, isLoading } = useAuth();
  const [bookings, setBookings] = useState<BookingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) return;
    if (!token) return;
    fetchBookings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, isAuthenticated, isLoading]);

  const fetchBookings = () => {
    if (!token) return;
    setLoading(true);
    api.bookings
      .myBookings(token)
      .then(setBookings)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load bookings")
      )
      .finally(() => setLoading(false));
  };

  const handleUpdateStatus = async (id: string, newStatus: string) => {
    if (!token) return;
    setUpdatingId(id);
    
    // Optimistic UI update
    setBookings((prev) => 
      prev.map(b => b.id === id ? { ...b, status: newStatus } : b)
    );

    try {
      await api.bookings.updateStatus(id, newStatus, token);
      toast.success(`Booking marked as ${newStatus}`);
    } catch (err) {
      // Revert on error
      fetchBookings(); 
      toast.error(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setUpdatingId(null);
    }
  };

  if (!isAuthenticated && !isLoading) return null;

  const filteredBookings = bookings.filter((b) => {
    if (filter === "all") return true;
    if (filter === "pending") return b.status === "pending";
    if (filter === "active") return ["confirmed", "in_progress"].includes(b.status);
    if (filter === "completed") return ["completed", "cancelled"].includes(b.status);
    return true;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return <span className="bg-yellow-100 text-yellow-800 text-xs px-2.5 py-1 rounded-full border border-yellow-200 font-medium">Pending</span>;
      case "confirmed":
        return <span className="bg-blue-100 text-blue-800 text-xs px-2.5 py-1 rounded-full border border-blue-200 font-medium">Confirmed</span>;
      case "in_progress":
        return <span className="bg-indigo-100 text-indigo-800 text-xs px-2.5 py-1 rounded-full border border-indigo-200 font-medium">In Progress</span>;
      case "completed":
        return <span className="bg-green-100 text-green-800 text-xs px-2.5 py-1 rounded-full border border-green-200 font-medium">Completed</span>;
      case "cancelled":
        return <span className="bg-red-100 text-red-800 text-xs px-2.5 py-1 rounded-full border border-red-200 font-medium">Cancelled</span>;
      default:
        return <span className="bg-gray-100 text-gray-800 text-xs px-2.5 py-1 rounded-full border border-gray-200 font-medium">{status.toUpperCase()}</span>;
    }
  };

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-12 border-b border-gray-100 pb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 mb-2">Bookings</h1>
          <p className="text-slate-500 text-base max-w-2xl">Manage your service requests, track appointments, and effortlessly update the status of your ongoing jobs.</p>
        </div>
      </div>

      {error ? (
        <p className="text-red-600 bg-red-50 p-4 rounded-lg mb-6 border border-red-100">{error}</p>
      ) : null}

      <div className="flex space-x-3 mb-8 pb-3 overflow-x-auto scrollbar-hide">
        {["all", "pending", "active", "completed"].map((tab) => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            className={`px-6 py-2.5 text-sm font-semibold rounded-xl transition-all whitespace-nowrap border ${
              filter === tab
                ? "bg-slate-900 text-white border-slate-900 shadow-md"
                : "bg-white text-slate-600 border-gray-200 hover:border-slate-400 hover:bg-slate-50"
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center p-12 text-gray-500">
          <Loader2 className="w-8 h-8 animate-spin mb-4 text-slate-800" />
          <p>Loading your bookings...</p>
        </div>
      ) : filteredBookings.length === 0 ? (
        <Card className="border-dashed border-2 shadow-sm rounded-xl">
          <CardContent className="flex flex-col items-center justify-center p-12 text-center text-gray-500">
            <Calendar className="w-12 h-12 text-gray-300 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No bookings found</h3>
            <p className="mb-6 max-w-sm">
              You don&apos;t have any {filter !== "all" ? filter : ""} bookings yet.
            </p>
            {user?.role === "client" && (
              <Link
                href="/artisans"
                className="bg-blue-600 text-white px-5 py-2.5 rounded-lg font-medium hover:bg-blue-700 transition"
              >
                Find an Artisan
              </Link>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
          {filteredBookings.map((b) => (
            <Card key={b.id} className="rounded-2xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-lg hover:border-gray-300 transition-all flex flex-col">
              <CardHeader className="p-6 border-b border-gray-100 bg-slate-50/50 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-xl font-bold text-slate-900 leading-tight">
                    {b.service}
                  </CardTitle>
                </div>
                <div>{getStatusBadge(b.status)}</div>
              </CardHeader>
              <CardContent className="p-6 space-y-4 flex-1 flex flex-col">
                <div className="flex items-center text-sm text-slate-600 font-medium">
                  <User className="w-5 h-5 mr-3 text-slate-400" />
                  {user?.role === "client" ? `Artisan #${b.artisan_id}` : `Client #${b.client_id}`}
                </div>
                <div className="flex items-center text-sm text-slate-600 font-medium">
                  <Clock className="w-5 h-5 mr-3 text-slate-400" />
                  {b.date ? new Date(b.date).toLocaleDateString(undefined, {
                    weekday: 'short', month: 'short', day: 'numeric',
                    hour: 'numeric', minute: '2-digit'
                  }) : "Date not set"}
                </div>
                <div className="mt-4 bg-slate-100/70 p-4 rounded-xl flex justify-between items-center border border-slate-200">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">Est. Cost</span>
                  <span className="text-lg font-bold text-slate-900">
                    {b.estimated_cost != null ? `$${Number(b.estimated_cost).toFixed(2)}` : "—"}
                  </span>
                </div>
                
                {/* Actions */}
                <div className="pt-4 mt-auto flex flex-wrap gap-3">
                  {user?.role === "client" && (
                    <>
                      {b.status === "pending" && (
                        <button
                          onClick={() => handleUpdateStatus(b.id, "cancelled")}
                          disabled={updatingId === b.id}
                          className="flex-1 inline-flex items-center justify-center text-sm px-4 py-3 border border-red-200 text-red-700 bg-red-50 hover:bg-red-100 rounded-xl font-bold transition disabled:bg-gray-100 disabled:text-gray-400 shadow-sm"
                        >
                          <XCircle className="w-5 h-5 mr-2" /> Cancel
                        </button>
                      )}
                      {b.status === "in_progress" && (
                        <button
                          onClick={() => handleUpdateStatus(b.id, "completed")}
                          disabled={updatingId === b.id}
                          className="flex-1 inline-flex items-center justify-center text-sm px-4 py-3 border border-emerald-200 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-xl font-bold transition disabled:bg-gray-100 disabled:text-gray-400 shadow-sm"
                        >
                          <CheckCircle2 className="w-5 h-5 mr-2" /> Mark Complete
                        </button>
                      )}
                    </>
                  )}

                  {user?.role === "artisan" && (
                    <>
                      {b.status === "pending" && (
                        <>
                          <button
                            onClick={() => handleUpdateStatus(b.id, "confirmed")}
                            disabled={updatingId === b.id}
                            className="flex-1 inline-flex items-center justify-center text-sm px-4 py-3 border border-blue-200 text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-xl font-bold transition disabled:bg-gray-100 disabled:text-gray-400"
                          >
                            <CheckCircle2 className="w-5 h-5 mr-2" /> Confirm
                          </button>
                          <button
                            onClick={() => handleUpdateStatus(b.id, "cancelled")}
                            disabled={updatingId === b.id}
                            className="flex-none inline-flex items-center justify-center text-sm px-4 py-3 border border-red-200 text-red-700 hover:bg-red-50 rounded-xl font-bold transition disabled:bg-gray-100 disabled:text-gray-400"
                          >
                            Decline
                          </button>
                        </>
                      )}
                      {b.status === "confirmed" && (
                        <button
                          onClick={() => handleUpdateStatus(b.id, "in_progress")}
                          disabled={updatingId === b.id}
                          className="flex-1 inline-flex items-center justify-center text-sm px-4 py-3 border border-indigo-200 text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-xl font-bold transition disabled:bg-gray-100 disabled:text-gray-400"
                        >
                          Start Work
                        </button>
                      )}
                      {["confirmed", "in_progress"].includes(b.status) && (
                        <button
                          onClick={() => handleUpdateStatus(b.id, "cancelled")}
                          disabled={updatingId === b.id}
                          className="flex-none inline-flex items-center justify-center text-sm px-4 py-3 border border-red-200 text-red-700 hover:bg-red-50 rounded-xl font-bold transition disabled:bg-gray-100 disabled:text-gray-400"
                        >
                          Cancel
                        </button>
                      )}
                    </>
                  )}
                  
                  {user?.role === "client" && (
                     <Link
                      href={`/artisans/${b.artisan_id}`}
                      className="w-full mt-1 text-center text-sm text-blue-600 hover:text-blue-800 font-medium hover:underline p-1"
                    >
                      View Artisan Profile
                    </Link>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
