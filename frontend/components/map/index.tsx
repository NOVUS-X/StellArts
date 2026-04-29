import dynamic from "next/dynamic";

const ArtisanMap = dynamic(() => import("./ArtisanMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-slate-50 animate-pulse flex items-center justify-center rounded-2xl border border-blue-100">
      <div className="text-slate-400 flex flex-col items-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-4"></div>
        <span className="text-sm font-medium">Initializing Map...</span>
      </div>
    </div>
  ),
});

export default ArtisanMap;
