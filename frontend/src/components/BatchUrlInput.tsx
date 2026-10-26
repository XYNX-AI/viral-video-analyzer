"use client";

import { useMemo, useState } from "react";

interface BatchUrlInputProps {
  onSubmit: (urls: string[]) => void;
  loading?: boolean;
}

export default function BatchUrlInput({ onSubmit, loading }: BatchUrlInputProps) {
  const [value, setValue] = useState("");
  const urls = useMemo(
    () => value.split(/[\n,]/).map((url) => url.trim()).filter(Boolean),
    [value]
  );

  return (
    <div className="w-full max-w-2xl mx-auto">
      <textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="每行粘贴一个视频链接，支持抖音、TikTok、Instagram、YouTube、X 等平台，最多 50 条..."
        rows={6}
        className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-base text-gray-900 placeholder-gray-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
        disabled={loading}
      />
      <div className="mt-3 flex items-center justify-between">
        <span className="text-sm text-gray-500">已识别 {urls.length} 条链接</span>
        <button
          onClick={() => onSubmit(urls)}
          disabled={urls.length === 0 || urls.length > 50 || loading}
          className="rounded-xl bg-blue-600 px-6 py-3 font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "提交中..." : "批量分析"}
        </button>
      </div>
    </div>
  );
}
