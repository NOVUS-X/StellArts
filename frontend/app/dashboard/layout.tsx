"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../../context/AuthContext";
import Navbar from "../../components/ui/Navbar";
import { LayoutDashboard, Wallet, UserCircle, LogOut } from "lucide-react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading, user, logout } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login?redirect=/dashboard");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500 animate-pulse">Loading dashboard...</p>
      </div>
    );
  }

  const handleLogout = () => {
    logout();
    router.replace("/");
  };

  const navItems = [
    { name: "Bookings", href: "/dashboard/bookings", icon: LayoutDashboard },
    { name: "Payments", href: "/dashboard/payments", icon: Wallet },
    { name: "Profile", href: "/dashboard/profile", icon: UserCircle },
  ];

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 flex flex-col">
      <Navbar />
      
      <div className="flex-1 w-full px-4 sm:px-6 lg:px-8 flex pt-16 mt-4">
        {/* Sidebar for Desktop */}
        <aside className="w-64 flex-shrink-0 hidden md:flex flex-col border-r border-gray-200 pr-6 pb-6">
          <div className="sticky top-24">
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-6 px-3">
              {user?.role === "artisan" ? "Artisan Dashboard" : "Client Dashboard"}
            </h2>
            <nav className="space-y-1">
              {navItems.map((item) => {
                const isActive = pathname.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-slate-900 text-white"
                        : "text-gray-700 hover:bg-gray-100"
                    }`}
                  >
                    <Icon className={`w-5 h-5 ${isActive ? "text-slate-100" : "text-gray-400"}`} />
                    {item.name}
                  </Link>
                );
              })}
            </nav>

            <div className="mt-8 pt-8 border-t border-gray-100">
               <div className="flex items-center gap-3 px-3 mb-4">
                  <div className="w-9 h-9 rounded-full bg-slate-200 flex items-center justify-center text-slate-700 font-semibold">
                    {user?.full_name?.charAt(0).toUpperCase() || "U"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {user?.full_name || "User"}
                    </p>
                    <p className="text-xs text-gray-500 truncate">{user?.email}</p>
                  </div>
               </div>
               <button
                 onClick={handleLogout}
                 className="flex items-center gap-3 w-full px-3 py-2 text-sm font-medium text-red-600 rounded-lg hover:bg-red-50 transition-colors"
               >
                 <LogOut className="w-5 h-5" />
                 Log out
               </button>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 w-full p-4 sm:p-6 lg:pl-10 pb-20">
          {/* Mobile padding compensation since sidebar is hidden there */}
          <div className="md:hidden mb-6 flex space-x-2 overflow-x-auto pb-2 scrollbar-hide">
             {navItems.map((item) => {
                const isActive = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                      isActive
                        ? "bg-slate-900 text-white"
                        : "bg-white text-gray-700 border border-gray-200"
                    }`}
                  >
                    {item.name}
                  </Link>
                );
              })}
          </div>
          
          <div className="bg-white rounded-3xl shadow-sm border border-gray-100 min-h-[calc(100vh-14rem)] p-6 sm:p-10 lg:p-14">
            {children}
          </div>
        </main>
      </div>
      
      {/* Remove Footer from layout if it breaks the scroll? No, keeping it at the bottom. */}
    </div>
  );
}
