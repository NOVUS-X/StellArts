import { 
  TransactionBuilder, 
  Networks, 
  rpc, 
  xdr, 
  nativeToScVal, 
  Address,
  Asset,
  Operation,
  Transaction
} from "@stellar/stellar-sdk";

// These would normally be in a .env file
const ESCROW_CONTRACT_ID = process.env.NEXT_PUBLIC_ESCROW_CONTRACT_ID || "CCBAW6E7G2PZ7U5Q3PZ7U5Q3PZ7U5Q3PZ7U5Q3PZ7U5Q3PZ7U5Q3PZ"; 
const NATIVE_TOKEN_ADDRESS = "CDLZFC3SYJYDZT7K67VZ7K67VZ7K67VZ7K67VZ7K67VZ7K67VZ7K67VZ"; // Dummy for testnet XLM
const RPC_URL = "https://soroban-testnet.stellar.org";
const NETWORK_PASSPHRASE = Networks.TESTNET;

const rpcServer = new rpc.Server(RPC_URL);

/**
 * Builds a Soroban transaction to resolve a dispute.
 * 
 * @param address Authenticated Admin address
 * @param engagementId Escrow ID from the contract
 * @param winnerAddress Public key of the winner (Client or Artisan)
 * @returns Base64 XDR of the prepared (but unsigned) transaction
 */
export async function prepareArbitration(
  address: string,
  engagementId: number,
  winnerAddress: string
): Promise<string> {
  const account = await rpcServer.getAccount(address);
  
  // Build the initial transaction
  const tx = new TransactionBuilder(account, {
    fee: "1000",
    networkPassphrase: NETWORK_PASSPHRASE,
  })
    .addOperation(
      Operation.invokeContractFunction({
        contract: ESCROW_CONTRACT_ID,
        function: "arbitrate",
        args: [
          nativeToScVal(engagementId, { type: "u64" }),
          new Address(winnerAddress).toScVal(),
          new Address(NATIVE_TOKEN_ADDRESS).toScVal(),
        ],
      })
    )
    .setTimeout(30)
    .build();

  // Simulate to calculate fees and footprints
  const sim = await rpcServer.simulateTransaction(tx);
  
  if (rpc.Api.isSimulationError(sim)) {
    throw new Error(`Simulation failed: ${sim.error}`);
  }

  // Set the footprints and fees from simulation
  const preparedTx = await rpcServer.prepareTransaction(tx);
  
  return preparedTx.toXDR();
}

/**
 * Builds a Soroban transaction to release funds to the artisan.
 * 
 * @param address Authenticated Client address
 * @param engagementId Escrow ID from the contract
 * @returns Base64 XDR of the prepared (but unsigned) transaction
 */
export async function prepareRelease(
  address: string,
  engagementId: number
): Promise<string> {
  const account = await rpcServer.getAccount(address);
  
  const tx = new TransactionBuilder(account, {
    fee: "1000",
    networkPassphrase: NETWORK_PASSPHRASE,
  })
    .addOperation(
      Operation.invokeContractFunction({
        contract: ESCROW_CONTRACT_ID,
        function: "release",
        args: [
          nativeToScVal(engagementId, { type: "u64" }),
        ],
      })
    )
    .setTimeout(30)
    .build();

  const sim = await rpcServer.simulateTransaction(tx);
  
  if (rpc.Api.isSimulationError(sim)) {
    throw new Error(`Simulation failed: ${sim.error}`);
  }

  const preparedTx = await rpcServer.prepareTransaction(tx);
  return preparedTx.toXDR();
}

/**
 * Submits a signed transaction to the Soroban network.
 * 
 * @param signedXdr The signed transaction XDR from the wallet
 * @returns The transaction response
 */
export async function submitTransaction(signedXdr: string): Promise<any> {
  const tx = new Transaction(signedXdr, NETWORK_PASSPHRASE);
  const sendResp = await rpcServer.sendTransaction(tx);
  
  if (sendResp.status === "ERROR") {
    throw new Error(`Transaction submission failed: ${JSON.stringify(sendResp.errorResult)}`);
  }

  // Poll for status
  let statusResp = await rpcServer.getTransaction(sendResp.hash);
  while (statusResp.status === rpc.Api.GetTransactionStatus.NOT_FOUND || statusResp.status === rpc.Api.GetTransactionStatus.SUCCESS && !statusResp.resultXdr) {
      // Small delay
      await new Promise(r => setTimeout(r, 1000));
      statusResp = await rpcServer.getTransaction(sendResp.hash);
  }

  if (statusResp.status === rpc.Api.GetTransactionStatus.FAILED) {
    throw new Error("Transaction failed on-chain");
  }

  return statusResp;
}
