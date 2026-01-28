/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['camdocs.camden.gov.uk'],
  },
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || '/planning-ai',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
