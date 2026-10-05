import type { NextConfig } from "next";

import path from "node:path";

const nextConfig: NextConfig = {
  turbopack: {
    // APEX is a monorepo with two independent lockfiles (root and frontend).
    // Pin the workspace root so Next.js does not infer it from the wrong file
    // and warn on every build.
    root: path.resolve(import.meta.dirname, ".."),
  },
};

export default nextConfig;
