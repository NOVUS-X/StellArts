import React, { useCallback, useState } from 'react';
import { Upload, Image as ImageIcon, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface UploadAreaProps {
  onFilesSelected: (files: FileList) => void;
  isUploading: boolean;
}

const UploadArea: React.FC<UploadAreaProps> = ({ onFilesSelected, isUploading }) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isUploading) setIsDragging(true);
  }, [isUploading]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (isUploading) return;

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      onFilesSelected(files);
    }
  }, [onFilesSelected, isUploading]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(e.target.files);
      // Reset input value to allow selecting same file again
      e.target.value = '';
    }
  };

  const openFileDialog = () => {
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={openFileDialog}
      className={cn(
        "relative border-2 border-dashed rounded-xl p-8 transition-all duration-200 cursor-pointer flex flex-col items-center justify-center gap-3 min-h-[200px]",
        isDragging 
          ? "border-blue-500 bg-blue-50/50 scale-[1.01]" 
          : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/50",
        isUploading && "opacity-50 cursor-not-allowed pointer-events-none"
      )}
    >
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        multiple
        className="hidden"
      />
      
      <div className={cn(
        "p-4 rounded-full bg-slate-100 text-slate-500 transition-transform duration-200",
        isDragging && "scale-110 text-blue-500 bg-blue-100"
      )}>
        <Upload size={32} />
      </div>

      <div className="text-center">
        <p className="text-lg font-semibold text-slate-700">
          {isDragging ? "Drop images here" : "Click or drag images to upload"}
        </p>
        <p className="text-sm text-slate-500 mt-1">
          Supports JPG, PNG, WebP (Max 10MB per file)
        </p>
      </div>

      {isUploading && (
        <div className="absolute inset-0 bg-white/20 backdrop-blur-[1px] flex items-center justify-center rounded-xl">
          <div className="bg-white px-4 py-2 rounded-full shadow-md text-sm font-medium flex items-center gap-2">
            <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            Processing...
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadArea;
