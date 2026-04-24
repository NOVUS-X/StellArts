"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Camera, Loader2, Save, X } from "lucide-react";
import Cropper from "react-easy-crop";
import { toast } from "sonner";

import Navbar from "../../../../components/ui/Navbar";
import Footer from "../../../../components/ui/Footer";
import { Button } from "../../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../../../../components/ui/card";
import { useAuth } from "../../../../context/AuthContext";
import { api, UserOut, ArtisanItem } from "../../../../lib/api";
import getCroppedImg from "../../../../lib/cropImage";

export default function ProfileEditPage() {
  const router = useRouter();
  const { user, token, isLoading: authLoading, setUser } = useAuth();
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [artisanProfile, setArtisanProfile] = useState<ArtisanItem | null>(null);
  
  // Form states
  const [fullName, setFullName] = useState("");
  const [bio, setBio] = useState("");
  const [specialties, setSpecialties] = useState<string[]>([]);
  const [specialtyInput, setSpecialtyInput] = useState("");
  const [location, setLocation] = useState("");
  
  // Avatar states
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isCropModalOpen, setIsCropModalOpen] = useState(false);
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);
  const [tempImage, setTempImage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login?redirect=/dashboard/profile/edit");
      return;
    }

    if (user && token) {
      setFullName(user.full_name || "");
      setAvatarPreview(user.avatar || null);
      
      if (user.role === "artisan") {
        api.artisans.me(token)
          .then((profile) => {
            setArtisanProfile(profile);
            setBio(profile.description || "");
            setLocation(profile.location || "");
            
            if (Array.isArray(profile.specialties)) {
              setSpecialties(profile.specialties);
            } else if (typeof profile.specialties === "string") {
              try {
                setSpecialties(JSON.parse(profile.specialties));
              } catch {
                setSpecialties(profile.specialties ? [profile.specialties] : []);
              }
            }
          })
          .catch((err) => {
            console.error("Error fetching artisan profile:", err);
          })
          .finally(() => setLoading(false));
      } else {
        setLoading(false);
      }
    }
  }, [user, token, authLoading, router]);

  const onCropComplete = useCallback((_croppedArea: any, croppedAreaPixels: any) => {
    setCroppedAreaPixels(croppedAreaPixels);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.addEventListener("load", () => {
        setTempImage(reader.result as string);
        setIsCropModalOpen(true);
      });
      reader.readAsDataURL(file);
    }
  };

  const handleCropSave = async () => {
    try {
      if (!tempImage || !croppedAreaPixels) return;
      
      const croppedBlob = await getCroppedImg(tempImage, croppedAreaPixels);
      if (croppedBlob) {
        const file = new File([croppedBlob], "avatar.jpg", { type: "image/jpeg" });
        setSelectedFile(file);
        setAvatarPreview(URL.createObjectURL(croppedBlob));
        setIsCropModalOpen(false);
      }
    } catch (e) {
      console.error(e);
      toast.error("Failed to crop image");
    }
  };

  const handleAddSpecialty = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && specialtyInput.trim()) {
      e.preventDefault();
      if (!specialties.includes(specialtyInput.trim())) {
        setSpecialties([...specialties, specialtyInput.trim()]);
      }
      setSpecialtyInput("");
    }
  };

  const removeSpecialty = (index: number) => {
    setSpecialties(specialties.filter((_, i) => i !== index));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setSaving(true);
    try {
      let currentAvatar = user?.avatar || null;
      if (selectedFile) {
        const updatedUserWithAvatar = await api.users.uploadAvatar(selectedFile, token);
        currentAvatar = updatedUserWithAvatar.avatar;
      }

      const updatedUser = await api.users.updateMe({ full_name: fullName }, token);
      setUser({ ...updatedUser, avatar: currentAvatar });

      if (user?.role === "artisan") {
        await api.artisans.updateProfile({
          description: bio,
          specialties: specialties,
          location: location,
        }, token);
      }

      toast.success("Profile updated successfully");
      router.refresh();
    } catch (err: any) {
      toast.error(err.message || "Failed to update profile");
    } finally {
      setSaving(false);
    }
  };

  const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace("/api/v1", "");

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />
      <main className="flex-grow pt-24 pb-16 px-4">
        <div className="max-w-3xl mx-auto">
          <Link
            href="/dashboard"
            className="inline-flex items-center text-sm text-gray-500 hover:text-blue-600 mb-6 transition-colors"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to Dashboard
          </Link>

          <div className="flex flex-col md:flex-row gap-8">
            <div className="w-full md:w-64 shrink-0">
              <Card className="overflow-hidden border-none shadow-sm bg-white">
                <CardContent className="p-6 flex flex-col items-center">
                  <div className="relative group cursor-pointer" onClick={() => fileInputRef.current?.click()}>
                    <div className="w-32 h-32 rounded-full overflow-hidden border-4 border-gray-50 shadow-sm bg-gray-100 flex items-center justify-center">
                      {avatarPreview ? (
                        <img src={avatarPreview.startsWith("/") ? `${apiBaseUrl}${avatarPreview}` : avatarPreview} alt="Avatar" className="w-full h-full object-cover" />
                      ) : (
                        <div className="text-4xl font-bold text-gray-300">
                          {fullName?.charAt(0) || user?.email?.charAt(0)}
                        </div>
                      )}
                    </div>
                    <div className="absolute inset-0 bg-black/40 rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <Camera className="w-8 h-8 text-white" />
                    </div>
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileChange}
                      accept="image/*"
                      className="hidden"
                    />
                  </div>
                  <h3 className="mt-4 font-semibold text-gray-900">{fullName || "Anonymous"}</h3>
                  <p className="text-xs text-gray-500 uppercase tracking-wider mt-1">{user?.role}</p>
                </CardContent>
              </Card>
            </div>

            <div className="flex-grow">
              <form onSubmit={handleSave} className="space-y-6">
                <Card className="border-none shadow-sm bg-white">
                  <CardHeader>
                    <CardTitle>Personal Information</CardTitle>
                    <CardDescription>Update your public identity on StellArts.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <label htmlFor="fullName" className="text-sm font-medium text-gray-700">Full Name</label>
                      <input
                        id="fullName"
                        type="text"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        className="w-full px-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                        placeholder="e.g. John Doe"
                        required
                      />
                    </div>
                  </CardContent>
                </Card>

                {user?.role === "artisan" && (
                  <Card className="border-none shadow-sm bg-white">
                    <CardHeader>
                      <CardTitle>Artisan Details</CardTitle>
                      <CardDescription>These details are visible on your public artisan profile.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="space-y-2">
                        <label htmlFor="bio" className="text-sm font-medium text-gray-700">Bio / Description</label>
                        <textarea
                          id="bio"
                          value={bio}
                          onChange={(e) => setBio(e.target.value)}
                          className="w-full px-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none min-h-[120px]"
                          placeholder="Tell us about your work and experience..."
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="text-sm font-medium text-gray-700">Specialties</label>
                        <div className="flex flex-wrap gap-2 mb-2">
                          {specialties.map((spec, index) => (
                            <span key={index} className="inline-flex items-center px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-medium">
                              {spec}
                              <button
                                type="button"
                                onClick={() => removeSpecialty(index)}
                                className="ml-1.5 hover:text-blue-900"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </span>
                          ))}
                        </div>
                        <input
                          type="text"
                          value={specialtyInput}
                          onChange={(e) => setSpecialtyInput(e.target.value)}
                          onKeyDown={handleAddSpecialty}
                          className="w-full px-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                          placeholder="Type and press Enter to add specialties"
                        />
                      </div>

                      <div className="space-y-2">
                        <label htmlFor="location" className="text-sm font-medium text-gray-700">Location</label>
                        <input
                          id="location"
                          type="text"
                          value={location}
                          onChange={(e) => setLocation(e.target.value)}
                          className="w-full px-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                          placeholder="e.g. Lagos, Nigeria"
                        />
                      </div>
                    </CardContent>
                  </Card>
                )}

                <div className="flex justify-end pt-4">
                  <Button
                    type="submit"
                    disabled={saving}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-2 h-auto rounded-full shadow-lg transition-all disabled:opacity-50"
                  >
                    {saving ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4 mr-2" />
                        Save Changes
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </main>
      <Footer />

      {isCropModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <Card className="w-full max-w-lg bg-white overflow-hidden shadow-2xl">
            <CardHeader className="border-b">
              <CardTitle>Crop Avatar</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="relative h-80 w-full bg-gray-900">
                <Cropper
                  image={tempImage!}
                  crop={crop}
                  zoom={zoom}
                  aspect={1}
                  onCropChange={setCrop}
                  onCropComplete={onCropComplete}
                  onZoomChange={setZoom}
                />
              </div>
              <div className="p-6 space-y-4">
                <div className="space-y-2">
                  <label className="text-xs text-gray-500 font-medium uppercase tracking-wider">Zoom</label>
                  <input
                    type="range"
                    value={zoom}
                    min={1}
                    max={3}
                    step={0.1}
                    aria-labelledby="Zoom"
                    onChange={(e) => setZoom(Number(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                </div>
                <div className="flex justify-end gap-3">
                  <Button
                    variant="ghost"
                    onClick={() => setIsCropModalOpen(false)}
                    className="rounded-full"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCropSave}
                    className="bg-blue-600 hover:bg-blue-700 text-white rounded-full px-6"
                  >
                    Done
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
