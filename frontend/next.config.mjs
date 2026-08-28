import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * These packages contain native Node.js bindings or Node-only dependencies
 * that webpack cannot bundle for the browser. We alias them to `false` in
 * the client build so the import chain is cut before webpack tries to resolve
 * their internals.
 *
 * Chain 1: soroban.ts → @stellar/stellar-sdk → sodium-native → bare-addon-resolve
 * Chain 2: WalletContext → stellar-wallets-kit → @hot-wallet/sdk → @near-js/utils → mustache
 */
const CLIENT_STUB_PACKAGES = [
  "sodium-native",
  "require-addon",
  "bare-addon-resolve",
  "mustache",
  "@near-js/utils",
  "@hot-wallet/sdk",
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: __dirname,
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
    ],
  },
  // Keep @stellar/stellar-sdk in Node-land only — never SSR/edge bundled.
  serverExternalPackages: ["@stellar/stellar-sdk", "sodium-native"],
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // Stub out Node built-ins referenced by stellar packages.
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
        crypto: false,
        path: false,
        os: false,
        stream: false,
        buffer: false,
        child_process: false,
      };

      // Alias every problem package to false so webpack stops tracing into them.
      config.resolve.alias = {
        ...config.resolve.alias,
        ...Object.fromEntries(CLIENT_STUB_PACKAGES.map((pkg) => [pkg, false])),
      };
    }
    return config;
  },
  async headers() {
    return [
      {
        // Never let the browser/CDN cache the SW file itself — the browser
        // must always fetch a fresh sw.js to detect updates. Service-Worker-
        // Allowed widens scope to root even though the file lives at /sw.js.
        source: "/sw.js",
        headers: [
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
    ];
  },
};

export default nextConfig;
