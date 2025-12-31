/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: '/approval-check',
  reactStrictMode: true,
  images: {
    domains: ['camdocs.camden.gov.uk'],
  },
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
