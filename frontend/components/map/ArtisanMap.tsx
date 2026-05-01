"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.css";
import "leaflet-defaulticon-compatibility";
import Link from "next/link";
import { Star, Wrench, MapPin, ChevronRight, Clock } from "lucide-react";
import type { ArtisanItem } from "../../lib/api";
import Price from "../ui/Price";

// Custom icon for artisans
const createCustomIcon = (isAvailable: boolean) => {
  const color = isAvailable ? "#2563eb" : "#64748b"; // blue-600 or slate-500
  const svg = `
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M20 38c10-10 16-18.4 16-24a16 16 0 1 0-32 0c0 5.6 6 14 16 24z" fill="${color}"/>
      <circle cx="20" cy="14" r="8" fill="white"/>
      <g transform="translate(13, 7) scale(0.6)">
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.77 3.77z" fill="${color}"/>
      </g>
    </svg>
  `;
  
  return L.divIcon({
    html: svg,
    className: "custom-artisan-icon",
    iconSize: [40, 40],
    iconAnchor: [20, 40],
    popupAnchor: [0, -40],
  });
};

const defaultIcon = createCustomIcon(true);
const unavailableIcon = createCustomIcon(false);

interface ArtisanMapProps {
  artisans: ArtisanItem[];
  center: [number, number];
  zoom?: number;
}

function ChangeView({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
}

export default function ArtisanMap({ artisans, center, zoom = 13 }: ArtisanMapProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return (
    <div className="w-full h-full bg-slate-50 animate-pulse flex items-center justify-center">
      <div className="text-slate-400 flex flex-col items-center">
        <Wrench className="w-8 h-8 mb-2" />
        <span className="text-sm font-medium">Loading Map...</span>
      </div>
    </div>
  );

  return (
    <div className="w-full h-full relative rounded-2xl overflow-hidden border border-blue-100 shadow-inner">
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={true}
        className="w-full h-full z-0"
      >
        <ChangeView center={center} zoom={zoom} />
        
        {/* Clean, premium look with CartoDB Positron tiles */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />

        {artisans.map((artisan) => {
          if (artisan.latitude == null || artisan.longitude == null) return null;
          
          return (
            <Marker
              key={artisan.id}
              position={[artisan.latitude, artisan.longitude]}
              icon={artisan.is_available ? defaultIcon : unavailableIcon}
            >
              <Popup className="artisan-popup">
                <div className="w-64 p-1">
                  <div className="flex items-start gap-3 mb-3">
                    <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center shrink-0 border border-blue-100">
                      <Wrench className="w-6 h-6 text-blue-600" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-bold text-gray-900 truncate leading-tight">
                        {artisan.business_name || "Artisan"}
                      </h3>
                      <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3" />
                        <span className="truncate">{artisan.location || "Nearby"}</span>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between mb-4 bg-slate-50 p-2 rounded-lg">
                    <div className="flex flex-col">
                      <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold">Rating</span>
                      <div className="flex items-center gap-1 text-amber-600 font-bold text-sm">
                        <Star className="w-3.5 h-3.5 fill-amber-500 text-amber-500" />
                        {artisan.rating ? Number(artisan.rating).toFixed(1) : "N/A"}
                      </div>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold">Rate</span>
                      <div className="text-blue-600 font-bold text-sm">
                        {artisan.hourly_rate ? <Price amount={Number(artisan.hourly_rate)} /> : "---"}/hr
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mb-4">
                    {artisan.is_available ? (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full">
                        <Clock className="w-3 h-3" />
                        AVAILABLE NOW
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-slate-500 bg-slate-100 px-2 py-1 rounded-full">
                        <Clock className="w-3 h-3" />
                        OFFLINE
                      </span>
                    )}
                    {artisan.distance_km != null && (
                      <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded-full">
                        {Number(artisan.distance_km).toFixed(1)} KM AWAY
                      </span>
                    )}
                  </div>

                  <Link 
                    href={`/artisans/${artisan.id}`}
                    className="flex items-center justify-center gap-2 w-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold py-2.5 rounded-xl transition-all shadow-md shadow-blue-100"
                  >
                    View Profile
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Map Overlay for total count */}
      <div className="absolute top-4 left-4 z-[10] pointer-events-none">
        <div className="bg-white/90 backdrop-blur-md border border-white/50 shadow-lg px-4 py-2.5 rounded-2xl flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white shadow-sm">
            <MapPin className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-blue-600 uppercase tracking-widest">Discovery Map</p>
            <p className="text-xs font-bold text-slate-800">
              {artisans.length} {artisans.length === 1 ? 'Artisan' : 'Artisans'} Found
            </p>
          </div>
        </div>
      </div>
      
      <style jsx global>{`
        .artisan-popup .leaflet-popup-content-wrapper {
          border-radius: 1.25rem;
          padding: 0.25rem;
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        }
        .artisan-popup .leaflet-popup-content {
          margin: 0.75rem;
        }
        .artisan-popup .leaflet-popup-tip {
          background: white;
        }
      `}</style>
    </div>
  );
}
