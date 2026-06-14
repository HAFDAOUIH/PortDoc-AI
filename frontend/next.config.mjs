/** @type {import('next').NextConfig} */
const nextConfig = {
  // Same-origin proxy: the browser calls /api/* and Next forwards it to the FastAPI
  // backend server-side. This means ONE public tunnel (on :3000) exposes the whole app —
  // no second API URL, no CORS, and the browser never needs to reach :8000 directly.
  async rewrites() {
    const target = process.env.API_PROXY_TARGET || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${target}/:path*` }];
  },
};

export default nextConfig;
