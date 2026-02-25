"""Soroban smart contract integration service."""
import time
from typing import Any

from stellar_sdk import (
    Keypair,
    Network,
    SorobanServer,
    TransactionBuilder,
)
from stellar_sdk.exceptions import PrepareTransactionException
from stellar_sdk.soroban_rpc import SendTransactionStatus
from stellar_sdk import scval
from stellar_sdk import xdr as stellar_xdr

from app.core.config import settings


# Constants
SOROBAN_RPC_URL = settings.SOROBAN_RPC_URL
ESCROW_CONTRACT_ID = settings.ESCROW_CONTRACT_ID
REPUTATION_CONTRACT_ID = settings.REPUTATION_CONTRACT_ID
NETWORK_PASSPHRASE = Network.TESTNET_NETWORK_PASSPHRASE

# Initialize Soroban server
soroban_server = SorobanServer(SOROBAN_RPC_URL)


def invoke_contract_function(
    contract_id: str,
    function_name: str,
    args: list,
    source_keypair: Keypair,
) -> dict[str, Any]:
    """
    Build, simulate, sign, and submit a Soroban contract invocation.

    Args:
        contract_id: The contract ID to invoke
        function_name: Name of the function to call
        args: List of SCVal arguments
        source_keypair: Keypair for signing

    Returns:
        Dict containing transaction hash and status

    Raises:
        RuntimeError: If simulation or submission fails
        TimeoutError: If transaction confirmation times out
    """
    # Load source account
    source_account = soroban_server.load_account(
        source_keypair.public_key
    )

    # Build transaction
    tx = (
        TransactionBuilder(
            source_account=source_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=300,
        )
        .append_invoke_contract_function_op(
            contract_id=contract_id,
            function_name=function_name,
            parameters=args,
        )
        .build()
    )

    # Simulate transaction
    try:
        sim_response = soroban_server.simulate_transaction(tx)
    except Exception as e:
        raise RuntimeError(f"Simulation failed: {str(e)}")

    # Check for simulation errors
    if hasattr(sim_response, "error") and sim_response.error:
        raise RuntimeError(f"Simulation failed: {sim_response.error}")

    # Prepare transaction with simulation results
    try:
        tx = soroban_server.prepare_transaction(tx, sim_response)
    except PrepareTransactionException as e:
        raise RuntimeError(f"Transaction preparation failed: {str(e)}")

    # Sign transaction
    tx.sign(source_keypair)

    # Submit transaction
    send_response = soroban_server.send_transaction(tx)
    if send_response.status == SendTransactionStatus.ERROR:
        error_msg = f"Transaction failed: {send_response.error_result_xdr}"
        raise RuntimeError(error_msg)

    # Poll for confirmation (30 attempts, 2 seconds apart)
    for _ in range(30):
        get_response = soroban_server.get_transaction(send_response.hash)
        if get_response.status != "NOT_FOUND":
            return {
                "hash": send_response.hash,
                "status": get_response.status,
            }
        time.sleep(2)

    raise TimeoutError("Transaction not confirmed within 60 seconds")
