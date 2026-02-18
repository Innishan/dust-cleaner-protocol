"use client";

import React from "react";
import "@rainbow-me/rainbowkit/styles.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RainbowKitProvider, getDefaultConfig, darkTheme } from "@rainbow-me/rainbowkit";

import { WagmiProvider } from "wagmi";

// ✅ Custom Monad chain from env
const MONAD_CHAIN_ID = Number(process.env.NEXT_PUBLIC_CHAIN_ID || "0");
const MONAD_RPC_URL = process.env.NEXT_PUBLIC_RPC_URL || "";
const PROJECT_ID = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "";
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

const monad = {
  id: MONAD_CHAIN_ID,
  name: "Monad",
  nativeCurrency: { name: "MON", symbol: "MON", decimals: 18 },
  rpcUrls: {
    default: { http: [MONAD_RPC_URL] },
    public: { http: [MONAD_RPC_URL] },
  },
  blockExplorers: {
    default: { name: "Explorer", url: "https://example.com" }, // optional placeholder
  },
  testnet: true,
} as const;

const config = getDefaultConfig({
  appName: "Dust Cleaner Protocol",
  projectId: PROJECT_ID,
  chains: [monad],
  ssr: true,
  appUrl: APP_URL,
});

const queryClient = new QueryClient();

export function Providers({ children }: { children: React.ReactNode }) {
  // Helpful beginner-friendly runtime checks (won't break build)
  if (!MONAD_CHAIN_ID) console.warn("NEXT_PUBLIC_CHAIN_ID is missing or invalid");
  if (!MONAD_RPC_URL) console.warn("NEXT_PUBLIC_RPC_URL is missing");
  if (!PROJECT_ID) console.warn("NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID is missing");

  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider theme={darkTheme()}>{children}</RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}

