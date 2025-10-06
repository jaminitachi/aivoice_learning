/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ["localhost", "cdn-icons-png.flaticon.com", "i.pinimg.com"],
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/generated_images/**",
      },
    ],
    unoptimized: true, // 개발 환경에서 최적화 비활성화
  },
};

export default nextConfig;
