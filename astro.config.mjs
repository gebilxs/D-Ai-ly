import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://gebilxs.github.io",
  // Trailing slash required so BASE_URL joins as /D-Ai-ly/posts/ not /D-Ai-lyposts/
  base: "/D-Ai-ly/",
  trailingSlash: "always",
  output: "static",
});
