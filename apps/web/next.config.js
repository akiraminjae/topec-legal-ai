/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  webpack: (config) => {
    // 매뉴얼 Markdown(src/content/manuals/*.md)을 문자열로 그대로 import 합니다.
    // 파일이 번들에 포함되므로 standalone 이미지에서도 별도 복사 없이 동작합니다.
    config.module.rules.push({ test: /\.md$/, type: "asset/source" });
    return config;
  },
};

module.exports = nextConfig;
