"use client";

import { useState } from "react";

interface UrlInputProps {
  onSubmit: (url: string) => void;
  loading?: boolean;
}

export default function UrlInput({ onSubmit, loading }: UrlInputProps) {
  const [url, setUrl] = useState("");

  const isValid = /^https?:\/\/\S+$/i.test(url.trim());

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="flex gap-3">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onPaste={(e) => {
            const text = e.clipboardData.getData("text");
            // Extract the first URL from share text copied from a platform.
            const match = text.match(/https?:\/\/[^\s]+/i);
            if (match) {
              e.preventDefault();
              setUrl(match[0]);
            }
          }}
          placeholder="粘贴视频链接..."
          className="flex-1 px-4 py-3 rounded-xl border border-gray-200 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base"
          disabled={loading}
        />
        <button
          onClick={() => onSubmit(url)}
          disabled={!isValid || loading}
          className="px-6 py-3 rounded-xl bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {loading ? "分析中..." : "开始分析"}
        </button>
      </div>
      <p className="mt-2 text-sm text-gray-500">
        支持抖音、TikTok、Instagram、YouTube、X、Pinterest 等平台
      </p>
    </div>
  );
}
