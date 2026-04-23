"use client"

import React, { useState, useCallback } from 'react';
import axios from 'axios';
import imageCompression from 'browser-image-compression';
import ImageCard from './ImageCard';
import UploadArea from './UploadArea';
import UploadProgress, { UploadFile } from './UploadProgress';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';

interface PortfolioGalleryProps {
  initialImages?: string[];
  onImagesUpdate?: (urls: string[]) => void;
}

const PortfolioGallery: React.FC<PortfolioGalleryProps> = ({ 
  initialImages = [], 
  onImagesUpdate 
}) => {
  const [images, setImages] = useState<string[]>(initialImages);
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const compressImage = async (file: File) => {
    const options = {
      maxSizeMB: 1,
      maxWidthOrHeight: 1024,
      useWebWorker: true,
    };
    try {
      return await imageCompression(file, options);
    } catch (error) {
      console.error('Compression error:', error);
      return file;
    }
  };

  const uploadFile = async (uploadFile: UploadFile) => {
    const formData = new FormData();
    const compressedFile = await compressImage(uploadFile.file);
    formData.append('file', compressedFile);

    try {
      // Using a placeholder endpoint as requested. 
      // Replace with your actual endpoint like /api/portfolio/upload
      const response = await axios.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const progress = progressEvent.total
            ? (progressEvent.loaded / progressEvent.total) * 100
            : 0;
          
          setUploadFiles(prev => 
            prev.map(f => f.id === uploadFile.id ? { ...f, progress } : f)
          );
        },
      });

      const imageUrl = response.data.url; // Adjust based on your API response structure

      setUploadFiles(prev => 
        prev.map(f => f.id === uploadFile.id ? { ...f, status: 'completed', url: imageUrl, progress: 100 } : f)
      );

      setImages(prev => {
        const newImages = [...prev, imageUrl];
        onImagesUpdate?.(newImages);
        return newImages;
      });

    } catch (error) {
      console.error('Upload failed for', uploadFile.file.name, error);
      setUploadFiles(prev => 
        prev.map(f => f.id === uploadFile.id ? { ...f, status: 'error', error: 'Upload failed' } : f)
      );
    }
  };

  const handleFilesSelected = async (fileList: FileList) => {
    const newFiles: UploadFile[] = Array.from(fileList).map(file => ({
      id: Math.random().toString(36).substring(7),
      file,
      progress: 0,
      status: 'uploading'
    }));

    setUploadFiles(prev => [...prev, ...newFiles]);
    setIsUploading(true);

    // Process uploads in parallel
    await Promise.all(newFiles.map(file => uploadFile(file)));
    
    setIsUploading(false);
  };

  const removeUpload = (id: string) => {
    setUploadFiles(prev => prev.filter(f => f.id !== id));
  };

  return (
    <div className="space-y-8 w-full max-w-6xl mx-auto p-4">
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-slate-800">Portfolio Gallery</h2>
          {images.length > 0 && (
            <p className="text-sm text-slate-500">{images.length} images</p>
          )}
        </div>

        <UploadArea onFilesSelected={handleFilesSelected} isUploading={isUploading} />
        
        <UploadProgress files={uploadFiles} onRemove={removeUpload} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {images.map((url, index) => (
          <ImageCard key={`${url}-${index}`} url={url} />
        ))}
        
        {images.length === 0 && uploadFiles.length === 0 && (
          <div className="col-span-full py-20 text-center border-2 border-dashed border-slate-100 rounded-xl bg-slate-50/30">
            <div className="flex flex-col items-center gap-2 text-slate-400">
              <Plus size={40} strokeWidth={1.5} />
              <p className="text-lg font-medium">No images uploaded yet</p>
              <p className="text-sm">Upload your best work to showcase it here</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PortfolioGallery;
