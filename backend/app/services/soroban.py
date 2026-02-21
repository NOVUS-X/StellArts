"""
Soroban smart contract integration for StellArts.
Handles all interactions with Soroban contracts on the Stellar network.
"""
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

from stellar_sdk import (
    SorobanServer,
    Keypair,
    Network,
    TransactionBuilder,
    scval,
    xdr as stellar_xdr,
)
from stellar_sdk.soroban_rpc import SendTransactionStatus
from stellar_sdk.exceptions import SorobanRpcError
from stellar_sdk.contract import ContractClient

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Soroban configuration
SOROBAN_RPC_URL = settings.SOROBAN_RPC_URL if hasattr(settings, 'SOROBAN_RPC_URL') else "https://soroban-testnet.stellar.org"
ESCROW_CONTRACT_ID = getattr(settings, 'ESCROW_CONTRACT_ID', None)
REPUTATION_CONTRACT_ID = getattr(settings, 'REPUTATION_CONTRACT_ID', None)
ESCROW_SECRET = settings.STELLAR_ESCROW_SECRET

# Initialize keypair and server
ESCROW_KEYPAIR = Keypair.from_secret(ESCROW_SECRET)
soroban_server = SorobanServer(SOROBAN_RPC_URL)


def invoke_contract_function(
    contract_id: str,
    function_name: str,
    args: List[stellar_xdr.SCVal],
    source_keypair: Keypair,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    """
    Build, simulate, sign, and submit a Soroban contract invocation.
    
    Args:
        contract_id: The contract ID (C... format)
        function_name: Name of the contract function to call
        args: List of SCVal arguments
        source_keypair: Keypair of the transaction submitter
        timeout_seconds: Maximum time to wait for confirmation
    
    Returns:
        Dictionary with transaction hash, status, and result
    
    Raises:
        RuntimeError: If transaction fails
        TimeoutError: If transaction not confirmed within timeout
    """
    try:
        # Load source account
        source_account = soroban_server.load_account(source_keypair.public_key)
        
        # Build transaction
        tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
                base_fee=300,  # Increased for Soroban operations
            )
            .append_invoke_contract_function_op(
                contract_id=contract_id,
                function_name=function_name,
                parameters=args,
            )
            .build()
        )
        
        # Simulate transaction to get resource usage
        logger.info(f"Simulating {function_name} on contract {contract_id[:8]}...")
        sim_response = soroban_server.simulate_transaction(tx)
        
        if hasattr(sim_response, "error") and sim_response.error:
            error_msg = f"Simulation failed: {sim_response.error}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Prepare transaction with simulation results
        tx = soroban_server.prepare_transaction(tx, sim_response)
        tx.sign(source_keypair)
        
        # Submit transaction
        logger.info(f"Submitting {function_name} transaction...")
        send_response = soroban_server.send_transaction(tx)
        
        if send_response.status == SendTransactionStatus.ERROR:
            error_msg = f"Transaction failed: {send_response.error_result_xdr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Poll for confirmation
        tx_hash = send_response.hash
        logger.info(f"Transaction submitted with hash: {tx_hash}")
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            get_response = soroban_server.get_transaction(tx_hash)
            
            if get_response.status != "NOT_FOUND":
                logger.info(f"Transaction confirmed")
                return {
                    "hash": tx_hash,
                    "status": get_response.status,
                    "result": get_response.result_xdr if hasattr(get_response, "result_xdr") else None
                }
        
        raise TimeoutError(f"Transaction {tx_hash} not confirmed within {timeout_seconds} seconds")
        
    except SorobanRpcError as e:
        logger.error(f"Soroban RPC error: {str(e)}")
        raise RuntimeError(f"Soroban RPC error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in contract invocation: {str(e)}")
        raise


def initialize_escrow(
    client_address: str,
    artisan_address: str,
    amount_stroops: int,
    deadline_ledger: int,
) -> int:
    """
    Initialize a new escrow contract on-chain.
    
    Args:
        client_address: Stellar public key of the client
        artisan_address: Stellar public key of the artisan
        amount_stroops: Amount in stroops (1 XLM = 10,000,000 stroops)
        deadline_ledger: Ledger sequence number for deadline
    
    Returns:
        engagement_id from the contract
    """
    if not ESCROW_CONTRACT_ID:
        raise RuntimeError("ESCROW_CONTRACT_ID not configured")
    
    logger.info(f"Initializing escrow: client={client_address[:8]}..., artisan={artisan_address[:8]}...")
    
    # Convert Python types to Soroban SCVals
    args = [
        scval.to_address(client_address),
        scval.to_address(artisan_address),
        scval.to_int128(amount_stroops),
        scval.to_uint64(deadline_ledger),
    ]
    
    # Invoke contract
    result = invoke_contract_function(
        ESCROW_CONTRACT_ID,
        "initialize",
        args,
        ESCROW_KEYPAIR,  # Platform signs the initialization
    )
    
    # For now, we'll return a placeholder engagement_id
    # In production, you'd parse this from result["result"]
    # The contract returns u64, so we need to parse it
    engagement_id = 1  # TODO: Parse from result
    
    logger.info(f"Escrow initialized with engagement_id: {engagement_id}")
    return engagement_id


def build_deposit_transaction(
    engagement_id: int,
    client_address: str,
) -> str:
    """
    Build an unsigned transaction for the client to deposit funds.
    
    Args:
        engagement_id: The escrow engagement ID
        client_address: Client's Stellar address
    
    Returns:
        Base64-encoded unsigned transaction XDR
    """
    if not ESCROW_CONTRACT_ID:
        raise RuntimeError("ESCROW_CONTRACT_ID not configured")
    
    # Load client account to get sequence number
    client_account = soroban_server.load_account(client_address)
    
    args = [
        scval.to_uint64(engagement_id),
    ]
    
    # Build transaction without signing
    tx = (
        TransactionBuilder(
            source_account=client_account,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
            base_fee=300,
        )
        .append_invoke_contract_function_op(
            contract_id=ESCROW_CONTRACT_ID,
            function_name="deposit",
            parameters=args,
        )
        .build()
    )
    
    # Return unsigned XDR
    return tx.to_xdr()


def release_escrow(
    engagement_id: int,
) -> Dict[str, Any]:
    """
    Release funds from escrow to artisan.
    
    Args:
        engagement_id: The escrow engagement ID
    
    Returns:
        Transaction result
    """
    if not ESCROW_CONTRACT_ID:
        raise RuntimeError("ESCROW_CONTRACT_ID not configured")
    
    logger.info(f"Releasing escrow {engagement_id}")
    
    args = [
        scval.to_uint64(engagement_id),
    ]
    
    return invoke_contract_function(
        ESCROW_CONTRACT_ID,
        "release",
        args,
        ESCROW_KEYPAIR,
    )


def refund_escrow(
    engagement_id: int,
) -> Dict[str, Any]:
    """
    Refund funds from escrow to client.
    
    Args:
        engagement_id: The escrow engagement ID
    
    Returns:
        Transaction result
    """
    if not ESCROW_CONTRACT_ID:
        raise RuntimeError("ESCROW_CONTRACT_ID not configured")
    
    logger.info(f"Refunding escrow {engagement_id}")
    
    args = [
        scval.to_uint64(engagement_id),
    ]
    
    return invoke_contract_function(
        ESCROW_CONTRACT_ID,
        "refund",
        args,
        ESCROW_KEYPAIR,
    )


def rate_artisan_on_chain(
    artisan_address: str,
    stars: int,
) -> Dict[str, Any]:
    """
    Submit an on-chain rating for an artisan.
    
    Args:
        artisan_address: Artisan's Stellar address
        stars: Rating from 1-5
    
    Returns:
        Transaction result
    """
    if not REPUTATION_CONTRACT_ID:
        logger.warning("REPUTATION_CONTRACT_ID not configured - skipping on-chain rating")
        return {"status": "skipped", "reason": "contract not configured"}
    
    if not 1 <= stars <= 5:
        raise ValueError("Stars must be between 1 and 5")
    
    logger.info(f"Rating artisan {artisan_address[:8]}... with {stars} stars")
    
    args = [
        scval.to_address(artisan_address),
        scval.to_uint64(stars),
    ]
    
    return invoke_contract_function(
        REPUTATION_CONTRACT_ID,
        "rate_artisan",
        args,
        ESCROW_KEYPAIR,
    )


def get_artisan_stats(
    artisan_address: str,
) -> Tuple[int, int]:
    """
    Get on-chain reputation stats for an artisan.
    
    Args:
        artisan_address: Artisan's Stellar address
    
    Returns:
        Tuple of (average_score_scaled_by_100, review_count)
    """
    if not REPUTATION_CONTRACT_ID:
        logger.warning("REPUTATION_CONTRACT_ID not configured")
        return (0, 0)
    
    logger.info(f"Getting stats for artisan {artisan_address[:8]}...")
    
    args = [scval.to_address(artisan_address)]
    
    result = invoke_contract_function(
        REPUTATION_CONTRACT_ID,
        "get_stats",
        args,
        ESCROW_KEYPAIR,
    )
    
    # TODO: Parse stats from result_xdr
    # Should return (average_scaled_by_100, review_count)
    return (0, 0)