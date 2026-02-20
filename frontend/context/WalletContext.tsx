"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useEffect,
  ReactNode,
} from "react";

/** Minimal type for wallet kit — full module loaded only on client via dynamic import */
interface WalletKitInstance {
  openModal: (params: {
    onWalletSelected: (option: { id: string }) => void | Promise<void>;
  }) => Promise<void>;
  setWallet: (id: string) => void;
  getAddress: () => Promise<{ address: string }>;
  signTransaction: (
    xdr: string,
    opts?: { address?: string; networkPassphrase?: string }
  ) => Promise<{ signedTxXdr: string }>;
}

interface WalletContextType {
  address: string | null;
  isConnected: boolean;
  kit: WalletKitInstance | null;
  connect: () => Promise<void>;
  disconnect: () => void;
  signTransaction: (xdr: string) => Promise<string>;
}

const WalletContext = createContext<WalletContextType | null>(null);

const TESTNET_PASSPHRASE =
  "Test SDF Network ; September 2015";

export function WalletProvider({ children }: { children: ReactNode }) {
  const [address, setAddress] = useState<string | null>(null);
  const [kit, setKit] = useState<WalletKitInstance | null>(null);

  useEffect(() => {
    import("@creit.tech/stellar-wallets-kit").then(
      ({
        StellarWalletsKit: Kit,
        WalletNetwork,
        allowAllModules,
        FREIGHTER_ID,
      }) => {
        setKit(
          new Kit({
            network: WalletNetwork.TESTNET,
            selectedWalletId: FREIGHTER_ID,
            modules: allowAllModules(),
          })
        );
      }
    );
  }, []);

  const connect = useCallback(async () => {
    if (!kit) return;
    try {
      await kit.openModal({
        onWalletSelected: async (option) => {
          kit.setWallet(option.id);
          const { address: addr } = await kit.getAddress();
          setAddress(addr);
        },
      });
    } catch (err) {
      console.error("Wallet connection failed:", err);
    }
  }, [kit]);

  const disconnect = useCallback(() => {
    setAddress(null);
  }, []);

  const signTransaction = useCallback(
    async (xdr: string): Promise<string> => {
      if (!address) throw new Error("Wallet not connected");
      if (!kit) throw new Error("Wallet kit not ready");
      const { signedTxXdr } = await kit.signTransaction(xdr, {
        address,
        networkPassphrase: TESTNET_PASSPHRASE,
      });
      return signedTxXdr;
    },
    [kit, address]
  );

  const value = useMemo(
    () => ({
      address,
      isConnected: !!address,
      kit,
      connect,
      disconnect,
      signTransaction,
    }),
    [address, kit, connect, disconnect, signTransaction]
  );

  return (
    <WalletContext.Provider value={value}>{children}</WalletContext.Provider>
  );
}

export function useWallet(): WalletContextType {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error("useWallet must be used within a WalletProvider");
  return ctx;
}
