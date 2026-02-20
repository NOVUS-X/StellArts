"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "../../components/ui/Navbar";
import Footer from "../../components/ui/Footer";
import { Button } from "../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
import { useAuth } from "../../context/AuthContext";
import { ArrowLeft } from "lucide-react";

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login?redirect=/profile");
    }
  }, [isAuthenticated, isLoading, router]);

  if (!isAuthenticated && !isLoading) return null;

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="pt-24 pb-16 px-4 max-w-2xl mx-auto">
        <Link
          href="/dashboard"
          className="inline-flex items-center text-gray-600 hover:text-blue-600 mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Dashboard
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Profile</h1>
        <p className="text-gray-600 mb-8">
          Your account details. Artisan profile editing can be added here.
        </p>

        {user && (
          <Card>
            <CardHeader>
              <CardTitle>Account</CardTitle>
              <CardDescription>Email and role</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm">
                <span className="font-medium text-gray-700">Email:</span>{" "}
                {user.email}
              </p>
              <p className="text-sm">
                <span className="font-medium text-gray-700">Role:</span>{" "}
                {user.role}
              </p>
              {user.full_name && (
                <p className="text-sm">
                  <span className="font-medium text-gray-700">Name:</span>{" "}
                  {user.full_name}
                </p>
              )}
              {user.phone && (
                <p className="text-sm">
                  <span className="font-medium text-gray-700">Phone:</span>{" "}
                  {user.phone}
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </main>
      <Footer />
    </div>
  );
}
