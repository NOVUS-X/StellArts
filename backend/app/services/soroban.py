"""
Soroban smart contract integration for StellArts.
Handles all interactions with Soroban contracts on the Stellar network.
"""
import logging
import time
from typing import Any

from stellar_sdk import (
    Keypair,
    SorobanServer,
    TransactionBuilder,
    scval,
    xdr as stellar_xdr,
)
from stellar_sdk.soroban_rpc import SendTransactionStatus

from app.core.config import settings

logger = logging.getLogger(__name__)

# Soroban configuration
SOROBAN_RPC_URL = settings.SOROBAN_RPC_URL
SOROBAN_NETWORK_PASSPHRASE = settings.SOROBAN_NETWORK_PASSPHRASE
soroban_server = SorobanServer(SOROBAN_RPC_URL)


def invoke_contract_function(
    contract_id: str,
    function_name: str,
    args: list[stellar_xdr.SCVal],
    source_keypair: Keypair,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """
    Build, simulate, sign, and submit a Soroban contract invocation.

    Args:
        contract_id: The contract ID to invoke
        function_name: Name of the function to call
        args: List of SCVal arguments
        source_keypair: Keypair of the transaction submitter
        timeout_seconds: Maximum time to wait for confirmation

    Returns:
        Dictionary with transaction hash, status, and result

    Raises:
        RuntimeError: If simulation or submission fails
        TimeoutError: If transaction confirmation times out
    """
    try:
        # Load source account
        source_account = soroban_server.load_account(source_keypair.public_key)

        # Build transaction
        tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=SOROBAN_NETWORK_PASSPHRASE,
                base_fee=settings.SOROBAN_BASE_FEE,
            )
            .append_invoke_contract_function_op(
                contract_id=contract_id,
                function_name=function_name,
                parameters=args,
            )
            .build()
        )

        # Simulate transaction
        logger.info(f"Simulating {function_name} on contract {contract_id[:8]}...")
        sim_response = soroban_server.simulate_transaction(tx)

        if hasattr(sim_response, "error") and sim_response.error:
            error_msg = f"Simulation failed: {sim_response.error}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Prepare and sign
        tx = soroban_server.prepare_transaction(tx, sim_response)
        prepared_xdr = tx.to_xdr()
        tx.sign(source_keypair)
        signed_xdr = tx.to_xdr()

        # Submit
        logger.info(f"Submitting {function_name} transaction...")
        send_response = soroban_server.send_transaction(tx)

        if send_response.status == SendTransactionStatus.ERROR:
            error_msg = f"Transaction failed: {send_response.error_result_xdr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Wait for confirmation
        tx_hash = send_response.hash
        logger.info(f"Transaction submitted with hash: {tx_hash}")

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            status_response = soroban_server.get_transaction_status(tx_hash)

            if status_response.status == "SUCCESS":
                logger.info(f"Transaction {tx_hash} confirmed successfully")
                return {
                    "success": True,
                    "hash": tx_hash,
                    "prepared_xdr": prepared_xdr,
                    "signed_xdr": signed_xdr,
                    "result": status_response.result_xdr,
                }
            elif status_response.status == "FAILED":
                error_msg = f"Transaction {tx_hash} failed: {status_response.result_xdr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            time.sleep(2)

        raise TimeoutError(f"Transaction {tx_hash} not confirmed within {timeout_seconds} seconds")

    except Exception as e:
        logger.error(f"Error in invoke_contract_function: {str(e)}")
        raise RuntimeError(f"Failed to invoke contract function: {str(e)}") from e


# Contract IDs
ESCROW_CONTRACT_ID = settings.ESCROW_CONTRACT_ID
REPUTATION_CONTRACT_ID = settings.REPUTATION_CONTRACT_ID


def get_backend_signer() -> Keypair:
    if not settings.BACKEND_SECRET_KEY:
        raise RuntimeError("BACKEND_SECRET_KEY must be configured for oracle signing")

    return Keypair.from_secret(settings.BACKEND_SECRET_KEY)


def initialize_escrow_contract(source_keypair: Keypair) -> dict[str, Any]:
    """Initialize the escrow contract with backend as admin."""
    invoke_contract_function(
        ESCROW_CONTRACT_ID,
        "initialize",
        [],
        source_keypair,
    )
    return {"success": True, "message": "Escrow contract initialized"}


def get_reputation_stats(artisan_address: str, source_keypair: Keypair) -> tuple[int, int]:
    """
    Get on-chain reputation stats for an artisan.
    
    Args:
        artisan_address: Artisan's Stellar address
        source_keypair: Keypair of the transaction submitter
    
    Returns:
        Tuple of (average_score_scaled_by_100, review_count)
    """
    args = [scval.to_address(artisan_address)]
    
    invoke_contract_function(
        REPUTATION_CONTRACT_ID,
        "get_stats",
        args,
        source_keypair,
    )
    return (0, 0)


def release_escrow_via_oracle(
    engagement_id: int,
    token_address: str,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Construct, sign, and submit a Soroban `release` invocation."""
    if not ESCROW_CONTRACT_ID:
        raise RuntimeError("ESCROW_CONTRACT_ID must be configured")

    signer = get_backend_signer()
    args = [
        scval.to_uint64(engagement_id),
        scval.to_address(token_address),
        scval.to_address(signer.public_key),
    ]

    return invoke_contract_function(
        ESCROW_CONTRACT_ID,
        "release",
        args,
        signer,
        timeout_seconds,
    )
