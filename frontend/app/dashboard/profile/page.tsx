"use client";

import { useAuth } from "../../../context/AuthContext";
import { User, Mail, Phone, Shield, BadgeCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";

export default function DashboardProfilePage() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
        <p className="text-gray-500">Manage your personal information and account settings</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-1 border-gray-100 shadow-sm">
          <CardContent className="pt-8 pb-6 flex flex-col items-center">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center text-blue-600 font-bold text-3xl border-4 border-white shadow-md mb-4">
              {user?.full_name?.[0] || user?.email?.[0]?.toUpperCase() || "U"}
            </div>
            <h2 className="text-xl font-bold text-gray-900">{user?.full_name || "User"}</h2>
            <p className="text-sm text-gray-500 capitalize">{user?.role || "Member"}</p>
            
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                <BadgeCheck className="w-3 h-3" />
                Verified
              </span>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                <Shield className="w-3 h-3" />
                {user?.role === "artisan" ? "Artisan Pro" : "Client"}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-2 border-gray-100 shadow-sm">
          <CardHeader>
            <CardTitle>Account Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-1">
                <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Full Name</p>
                <div className="flex items-center gap-2 text-gray-900">
                  <User className="w-4 h-4 text-gray-400" />
                  {user?.full_name || "Not set"}
                </div>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Email Address</p>
                <div className="flex items-center gap-2 text-gray-900">
                  <Mail className="w-4 h-4 text-gray-400" />
                  {user?.email}
                </div>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Phone Number</p>
                <div className="flex items-center gap-2 text-gray-900">
                  <Phone className="w-4 h-4 text-gray-400" />
                  {user?.phone || "Not set"}
                </div>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Username</p>
                <div className="flex items-center gap-2 text-gray-900">
                  <span className="text-gray-400">@</span>
                  {user?.username || "Not set"}
                </div>
              </div>
            </div>
            
            <div className="pt-6 border-t border-gray-100">
              <Button variant="outline" className="rounded-xl">
                Edit Profile
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
