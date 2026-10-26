"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getBatchResults, getExcelUrl } from "@/lib/api";
import { BatchAnalysisResult } from "@/types";
import ProgressStream from "@/components/ProgressStream";

export default function BatchAnalysisPage() {
  const params = useParams();
  const taskId = params.taskId as string;
  const [result, setResult] = useState<BatchAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadResults = useCallback(async (reportError = true) => {
    try {
      setResult(await getBatchResults(taskId));
    } catch {
      if (reportError) setError("获取批量结果失败");
    }
  }, [taskId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadResults(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadResults]);

  if (!result && !error) {
    return (
      <main className="flex flex-1 items-center justify-center bg-gray-50 px-4">
        <ProgressStream taskId={taskId} onComplete={() => loadResults(true)} onError={setError} />
      </main>
    );
  }

  return (
    <main className="min-h-screen flex-1 bg-gray-50 px-4 pb-16 pt-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <Link href="/" className="text-sm text-blue-500 hover:text-blue-700">&#8592; 返回首页</Link>
          {result && (
            <a href={getExcelUrl(taskId)} download className="rounded-lg border border-green-600 px-4 py-2 text-sm font-medium text-green-700 hover:bg-green-50">
              导出批量 Excel
            </a>
          )}
        </div>
        <h1 className="mb-2 text-2xl font-semibold text-gray-900">批量分析结果</h1>
        {error && <p className="mb-4 text-red-500">{error}</p>}
        {result && (
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
            <div className="border-b border-gray-100 px-4 py-3 text-sm text-gray-500">
              共 {result.items.length} 条，完成 {result.items.filter((item) => item.status === "completed").length} 条
            </div>
            <div className="divide-y divide-gray-100">
              {result.items.map((item) => (
                <div key={item.task_id} className="flex items-center justify-between gap-4 px-4 py-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-gray-800">{item.url}</p>
                    {item.error && <p className="mt-1 text-xs text-red-500">{item.error}</p>}
                  </div>
                  {item.status === "completed" ? (
                    <Link href={`/analysis/${item.task_id}`} className="shrink-0 text-sm text-blue-600 hover:text-blue-800">查看结果</Link>
                  ) : (
                    <span className="shrink-0 text-sm text-red-500">失败</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
