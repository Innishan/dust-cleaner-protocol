"use client";

import "@rainbow-me/rainbowkit/styles.css";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WagmiProvider } from "wagmi";
import { RainbowKitProvider, getDefaultConfig, darkTheme } from "@rainbow-me/rainbowkit";
import type { Chain } from "viem";

const queryClient = new QueryClient();

/**
 * ✅ Monad MAINNET only
 * chainId = 143
 * rpc = https://rpc.monad.xyz
 */
const monadMainnet: Chain = {
  id: 143,
  name: "Monad",
  nativeCurrency: { name: "MON", symbol: "MON", decimals: 18 },
  rpcUrls: {
    default: { http: ["https://rpc.monad.xyz"] },
    public: { http: ["https://rpc.monad.xyz"] },
  },
  blockExplorers: {
    default: { name: "Monad Explorer", url: "https://explorer.monad.xyz" },
  },
};

const projectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "";

// IMPORTANT: ssr should be false for App Router client-only wallet UI
const config = getDefaultConfig({
  appName: "Dust Cleaner Protocol",
  projectId,
  chains: [monadMainnet],
  ssr: false,
});

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider theme={darkTheme()}>{children}</RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}

// Optional default export if your layout imports default
export default Providers;

