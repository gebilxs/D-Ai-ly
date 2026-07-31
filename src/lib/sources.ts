export const SOURCES = [
  { id: "jiqizhixin", name: "机器之心", url: "https://www.jiqizhixin.com/" },
  { id: "qbitai", name: "量子位", url: "https://www.qbitai.com/" },
  { id: "geekpark", name: "极客公园", url: "https://www.geekpark.net/" },
  { id: "jazzyear", name: "甲子光年", url: "https://www.jazzyear.com/index.html" },
  { id: "sina_media", name: "新浪媒体号", url: "https://www.sina.cn/media/5703921756" },
  { id: "baai", name: "智源社区", url: "https://hub.baai.ac.cn/" },
] as const;

export function sourceName(id: string): string {
  return SOURCES.find((s) => s.id === id)?.name ?? id;
}

export function formatDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}
