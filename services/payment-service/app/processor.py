async def process_transaction(txn: dict) -> dict:
    # Simulate business logic
    result = {
        "txn_id": txn["txn_id"],
        "user_id": txn["user_id"],
        "amount": txn["amount"],
        "status": "approved",
        "processor_ref": f"ref_{txn['txn_id']}"
    }
    return result