import React from 'react';
import Image from 'next/image';
import { Card, CardContent } from '@/components/ui/card';

interface ImageCardProps {
  url: string;
  alt?: string;
}

const ImageCard: React.FC<ImageCardProps> = ({ url, alt = 'Portfolio image' }) => {
  return (
    <Card className="overflow-hidden group cursor-pointer border-none shadow-sm hover:shadow-md transition-shadow duration-300">
      <CardContent className="p-0 relative aspect-square">
        <Image
          src={url}
          alt={alt}
          fill
          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
          className="object-cover transition-transform duration-500 group-hover:scale-105"
        />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300" />
      </CardContent>
    </Card>
  );
};

export default ImageCard;
