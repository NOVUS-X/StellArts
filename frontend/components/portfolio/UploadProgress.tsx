import React from 'react';
import { Progress } from '@/components/ui/progress';
import { FileIcon, X, CheckCircle2, AlertCircle } from 'lucide-react';

export interface UploadFile {
  id: string;
  file: File;
  progress: number;
  status: 'uploading' | 'completed' | 'error';
  url?: string;
  error?: string;
}

interface UploadProgressProps {
  files: UploadFile[];
  onRemove?: (id: string) => void;
}

const UploadProgress: React.FC<UploadProgressProps> = ({ files, onRemove }) => {
  if (files.length === 0) return null;

  return (
    <div className="mt-4 space-y-3">
      {files.map((upload) => (
        <div 
          key={upload.id} 
          className="p-3 border rounded-lg bg-white shadow-sm flex items-start gap-3 transition-all animate-in fade-in slide-in-from-top-1"
        >
          <div className="p-2 bg-slate-100 rounded text-slate-500">
            <FileIcon size={20} />
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex justify-between items-center mb-1">
              <p className="text-sm font-medium truncate pr-4">
                {upload.file.name}
              </p>
              {onRemove && upload.status !== 'uploading' && (
                <button 
                  onClick={() => onRemove(upload.id)}
                  className="text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <X size={16} />
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              <div className="flex-1">
                <Progress 
                  value={upload.progress} 
                  className={`h-1.5 transition-all duration-300 ${
                    upload.status === 'error' ? '[&>div]:bg-red-500' : 
                    upload.status === 'completed' ? '[&>div]:bg-green-500' : ''
                  }`} 
                />
              </div>
              <span className="text-xs text-slate-500 tabular-nums w-8 text-right">
                {Math.round(upload.progress)}%
              </span>
            </div>

            <div className="mt-1 flex items-center gap-1.5">
              {upload.status === 'completed' && (
                <>
                  <CheckCircle2 size={12} className="text-green-500" />
                  <span className="text-xs text-green-600">Upload complete</span>
                </>
              )}
              {upload.status === 'error' && (
                <>
                  <AlertCircle size={12} className="text-red-500" />
                  <span className="text-xs text-red-600">{upload.error || 'Upload failed'}</span>
                </>
              )}
              {upload.status === 'uploading' && (
                <span className="text-xs text-slate-400 italic">Uploading...</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default UploadProgress;
