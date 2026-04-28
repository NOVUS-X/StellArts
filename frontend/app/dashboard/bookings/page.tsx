"use client";

import { useState, useEffect, useMemo } from "react";
import { api, type BookingResponse } from "../../../lib/api";
import { useAuth } from "../../../context/AuthContext";
import BookingCard from "../../../components/dashboard/BookingCard";
import { Search, Filter, Plus } from "lucide-react";
import Link from "next/link";
import PaymentModal from "../../../components/dashboard/PaymentModal";

type FilterStatus = "all" | "pending" | "active" | "completed";

export default function DashboardBookingsPage() {
  const { token, user } = useAuth();
  const [bookings, setBookings] = useState<BookingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeFilter, setActiveFilter] = useState<FilterStatus>("all");
  const [searchQuery, setSearchQuery] = useState("");
  
  const [selectedBookingForPayment, setSelectedBookingForPayment] = useState<BookingResponse | null>(null);

  useEffect(() => {
    if (!token) return;
    loadBookings();
  }, [token]);

  const loadBookings = async () => {
    setLoading(true);
    try {
      const data = await api.bookings.myBookings(token!);
      setBookings(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bookings");
    } finally {
      setLoading(false);
    }
  };

  const filteredBookings = useMemo(() => {
    return bookings.filter((b) => {
      const matchesSearch = b.service.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           b.artisan_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           b.client_name?.toLowerCase().includes(searchQuery.toLowerCase());
      
      if (activeFilter === "all") return matchesSearch;
      if (activeFilter === "pending") return matchesSearch && b.status === "pending";
      if (activeFilter === "active") return matchesSearch && (b.status === "confirmed" || b.status === "in_progress");
      if (activeFilter === "completed") return matchesSearch && b.status === "completed";
      return matchesSearch;
    });
  }, [bookings, activeFilter, searchQuery]);

  const handleStatusUpdate = (updatedBooking: BookingResponse) => {
    setBookings((prev) => 
      prev.map((b) => b.id === updatedBooking.id ? updatedBooking : b)
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bookings</h1>
          <p className="text-gray-500">Manage your service requests and schedules</p>
        </div>
        {user?.role === "client" && (
          <Link href="/artisans">
            <button className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl text-sm font-semibold transition-all shadow-sm shadow-blue-200">
              <Plus className="w-4 h-4" />
              New Booking
            </button>
          </Link>
        )}
      </div>

      <div className="flex flex-col md:flex-row gap-4 items-center justify-between bg-white p-2 rounded-2xl border border-gray-100 shadow-sm">
        <div className="flex p-1 bg-gray-50 rounded-xl w-full md:w-auto">
          {(["all", "pending", "active", "completed"] as FilterStatus[]).map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={classNames(
                "px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all",
                activeFilter === filter 
                  ? "bg-white text-blue-600 shadow-sm" 
                  : "text-gray-500 hover:text-gray-700"
              )}
            >
              {filter}
            </button>
          ))}
        </div>
        
        <div className="relative w-full md:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search bookings..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl border-none bg-gray-50 text-sm focus:ring-2 focus:ring-blue-500/20 transition-all"
          />
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-48 bg-gray-100 rounded-2xl" />
          ))}
        </div>
      ) : filteredBookings.length === 0 ? (
        <div className="bg-white border border-dashed border-gray-200 rounded-3xl p-12 text-center">
          <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <Filter className="w-8 h-8 text-gray-300" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900">No bookings found</h3>
          <p className="text-gray-500 mt-1 max-w-xs mx-auto">
            {searchQuery ? "Try adjusting your search or filters" : "You don't have any bookings in this category yet."}
          </p>
          {user?.role === "client" && !searchQuery && (
            <Link href="/artisans" className="mt-6 inline-block text-blue-600 font-semibold hover:underline">
              Find an artisan
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredBookings.map((booking) => (
            <BookingCard 
              key={booking.id} 
              booking={booking} 
              onStatusUpdate={handleStatusUpdate}
              onPayNow={(b) => setSelectedBookingForPayment(b)}
            />
          ))}
        </div>
      )}

      {selectedBookingForPayment && (
        <PaymentModal
          booking={selectedBookingForPayment}
          isOpen={!!selectedBookingForPayment}
          onClose={() => setSelectedBookingForPayment(null)}
          onSuccess={() => {
            loadBookings();
            setSelectedBookingForPayment(null);
          }}
        />
      )}
    </div>
  );
}

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}
