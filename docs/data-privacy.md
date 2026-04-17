# Data Privacy

## Tokenization

The API gateway now simulates PCI-aware tokenization for card payments.

- clients may submit `card_pan`
- the gateway converts that PAN into:
  - `payment_token`
  - `masked_pan`
  - `pan_fingerprint`
- raw `card_pan` is stripped before Kafka publication and is never written to ledger storage

This keeps the portfolio aligned with the requirement to avoid PAN storage while still demonstrating a financial-data handling pattern.

## GDPR Contact Deletion

P2P payments can now carry an optional `p2p_contact` object:

- `contact_id`
- `display_name`
- `email`

The ledger stores personal contact details in a separate contact record and keeps only `p2p_contact_id` on the immutable transaction entry.

GDPR-style deletion endpoint:

```text
DELETE /v1/contacts/{user_id}/{contact_id}
```

Deletion behavior:

- removes `display_name`
- removes `email`
- stamps `deleted_at`
- preserves immutable transaction history and contact identifier references
