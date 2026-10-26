"use client";

import { forwardRef, useImperativeHandle, useRef, useState } from "react";

export interface VideoPreviewHandle {
  seekTo: (time: number) => void;
}

interface VideoPreviewProps {
  src: string;
}

const VideoPreview = forwardRef<VideoPreviewHandle, VideoPreviewProps>(
  ({ src }, ref) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [unavailable, setUnavailable] = useState(false);

    useImperativeHandle(ref, () => ({
      seekTo: (time: number) => {
        if (videoRef.current) {
          videoRef.current.currentTime = time;
          videoRef.current.play().catch(() => {});
        }
      },
    }));

    // The backend deletes the downloaded source video once analysis finishes to
    // keep disk usage flat, so /api/video may legitimately 404 here.
    if (unavailable) {
      return (
        <div className="w-full rounded-xl bg-gray-900 text-gray-300 flex flex-col items-center justify-center aspect-video p-6 text-center">
          <span className="text-sm font-medium">原视频已清理</span>
          <span className="text-xs mt-2 text-gray-500 leading-relaxed">
            为节省服务器磁盘空间，分析完成后已删除源视频。
            <br />
            下方的画面截图和文字分析不受影响。
          </span>
        </div>
      );
    }

    return (
      <video
        ref={videoRef}
        src={src}
        controls
        className="w-full rounded-xl bg-black"
        playsInline
        onError={() => setUnavailable(true)}
      />
    );
  }
);

VideoPreview.displayName = "VideoPreview";
export default VideoPreview;
