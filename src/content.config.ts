import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const articles = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/articles" }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    source: z.string(),
    source_id: z.string(),
    url: z.string(),
    summary: z.string().default(""),
    tags: z.array(z.string()).default(["AI"]),
    article_id: z.string().optional(),
  }),
});

const digests = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/digests" }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    count: z.number().default(0),
    items: z
      .array(
        z.object({
          title: z.string(),
          slug: z.string(),
          source: z.string(),
          source_id: z.string(),
          url: z.string(),
          summary: z.string().default(""),
        }),
      )
      .default([]),
  }),
});

export const collections = { articles, digests };
