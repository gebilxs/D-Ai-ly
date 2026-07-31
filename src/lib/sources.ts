/** Public homepage links shown on the site / README (not crawl API endpoints). */
export type Source = {
  id: string;
  name: string;
  /** Primary homepage / 官网. */
  url: string;
  /**
   * When the homepage is behind a wall, optional public jump target
   * (e.g. official Weibo) shown next to the 官网 link.
   */
  jumpUrl?: string;
  jumpLabel?: string;
};

export const SOURCES: readonly Source[] = [
  {
    id: "jiqizhixin",
    name: "机器之心",
    url: "https://www.jiqizhixin.com/",
    // Homepage currently serves a data-service wall; keep 官网 + usable jump.
    jumpUrl: "https://weibo.com/synced",
    jumpLabel: "跳转官方微博",
  },
  { id: "qbitai", name: "量子位", url: "https://www.qbitai.com/" },
  { id: "geekpark", name: "极客公园", url: "https://www.geekpark.net/" },
  { id: "jazzyear", name: "甲子光年", url: "https://www.jazzyear.com/" },
  {
    id: "sina_media",
    name: "新智元",
    url: "https://www.sina.cn/media/5703921756",
  },
  { id: "baai", name: "智源社区", url: "https://hub.baai.ac.cn/" },
] as const;

export function sourceName(id: string): string {
  return SOURCES.find((s) => s.id === id)?.name ?? id;
}

export function formatDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}
