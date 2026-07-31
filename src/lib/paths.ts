/** Join a path onto Astro base, always with a single slash boundary. */
export function withBase(path = ""): string {
  const raw = import.meta.env.BASE_URL || "/";
  const base = raw.endsWith("/") ? raw : `${raw}/`;
  const cleaned = path.replace(/^\//, "");
  return cleaned ? `${base}${cleaned}` : base;
}
