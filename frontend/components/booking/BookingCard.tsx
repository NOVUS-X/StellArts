import {
  Card,
  CardHeader,
  CardContent,
  CardTitle,
  CardDescription,
} from "../ui/card";
import { cn } from "../../lib/utils";

export interface BookingProps {
  artisanName: string;
  service: string;
  date: Date;
  price: number;
  status: "pending" | "confirmed" | "in_progress" | "completed" | "cancelled";
}

const statusStyles = {
  pending: "bg-amber-50 text-amber-700 border-amber-200 ring-amber-500/10",
  confirmed: "bg-blue-50 text-blue-700 border-blue-200 ring-blue-500/10",
  in_progress:
    "bg-violet-50 text-violet-700 border-violet-200 ring-violet-500/10",
  completed:
    "bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-500/10",
  cancelled: "bg-red-50 text-red-700 border-red-200 ring-red-500/10",
};

export function BookingCard({
  artisanName,
  service,
  date,
  price,
  status,
}: BookingProps) {
  const formattedDate = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);

  const formattedPrice = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(price);

  return (
    <Card className="group w-full max-w-md cursor-pointer border border-gray-100 shadow-sm transition-all duration-300 hover:shadow-lg hover:border-blue-200 hover:-translate-y-1 bg-white relative overflow-hidden">
      {/* Texture Overlay */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: "radial-gradient(#4b5563 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      ></div>

      <CardHeader className="flex flex-row items-start justify-between pb-3 p-5 relative z-10">
        <div className="space-y-1.5 min-w-0">
          <CardTitle className="text-base font-bold text-gray-900 truncate pr-2 leading-tight">
            {service}
          </CardTitle>
          <CardDescription className="text-xs font-medium text-gray-500 flex items-center gap-1.5">
            <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-blue-500"></span>
            <span className="truncate">with {artisanName}</span>
          </CardDescription>
        </div>
        <div
          className={cn(
            "shrink-0 px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider shadow-sm ring-1 ring-inset",
            statusStyles[status],
          )}
        >
          {status}
        </div>
      </CardHeader>
      <CardContent className="p-5 pt-0 relative z-10">
        <div className="grid grid-cols-2 gap-4 mt-2 bg-gray-50/80 p-3 rounded-lg border border-gray-100 group-hover:bg-blue-50/50 transition-colors backdrop-blur-sm">
          <div className="flex flex-col space-y-0.5">
            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">
              Date & Time
            </span>
            <span className="text-sm font-semibold text-gray-700">
              {formattedDate}
            </span>
          </div>
          <div className="flex flex-col items-end space-y-0.5">
            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">
              Amount
            </span>
            <span className="text-lg font-bold text-blue-600 tracking-tight">
              {formattedPrice}
            </span>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-gray-100 hidden group-hover:flex items-center justify-between text-xs text-blue-600 font-medium transition-all">
          <span>Booking ID: #8X29B</span>
          <span className="group-hover:translate-x-1 transition-transform">
            View Details →
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
