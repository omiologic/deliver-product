# Deployment freshness

Use this contract before a credentialed, destructive, or release-significant
journey claims behavior from a shared environment. It does not apply to
source-only, component, contract, or local-loopback evidence and never
authorizes deployment.

## Receipt boundary

One receipt describes one exact environment and deployable unit. Its shape is
owned by [`deployment-receipt.schema.json`](deployment-receipt.schema.json):

- `environment` and `deployable_unit` isolate freshness; a receipt never
  transfers between environments or units;
- `endpoint` is the exact HTTPS target observed after deployment;
- `artifact_identity` hashes the deployed service, client, template, image, or
  bundle inputs selected by the deployment path;
- `public_configuration_identity` hashes applicable public client
  configuration, or is `null` when the unit has none;
- `source_identity` hashes the source and build inputs represented by the
  artifact;
- `deployment` retains a provider name and provider-native change-set,
  deployment, version, or invalidation identity; and
- `observed_at` records when the deployment result was observed.

Receipts contain identities, never source/configuration values, credentials,
tokens, request headers, query strings, or user information. A Git revision may
be retained separately for traceability, but cannot replace artifact, source,
or public-configuration comparison.

## Emit and retain

Deployment paths call the deterministic helper after the provider reports
success. `--output` atomically retains the receipt at an operator-selected
location; omitting it prints the JSON for an external workflow to retain.

```sh
python3 skills/delivery-spine/scripts/deployment_freshness.py emit \
  --environment staging \
  --deployable-unit wx-client \
  --endpoint https://example.test \
  --artifact-path interfaces/apps/wx-client/out \
  --public-config-identity <sha256> \
  --source-path interfaces/apps/wx-client \
  --deployment-provider aws-cloudfront \
  --deployment-receipt <invalidation-id> \
  --output <retained-receipt.json>
```

Select exact paths. Generated receipts must live outside every selected source,
artifact, and configuration path so writing a receipt does not invalidate its
own identity.

## Preflight

Recompute the same identities immediately before user interaction:

```sh
python3 skills/delivery-spine/scripts/deployment_freshness.py check \
  --receipt <retained-receipt.json> \
  --environment staging \
  --deployable-unit wx-client \
  --endpoint https://example.test \
  --artifact-path interfaces/apps/wx-client/out \
  --public-config-identity <sha256> \
  --source-path interfaces/apps/wx-client
```

The checker prints a bounded JSON result and exits `0` only for `FRESH`, `1`
for `STALE`, and `2` for `UNKNOWN` or invalid evidence. Missing receipts and
fields are `UNKNOWN`; exact mismatches are `STALE`. Stop the journey on either.

When the user explicitly asks to characterize a stale deployment, add
`--stale-diagnostic`. The command then exits `0` while retaining `STALE` or
`UNKNOWN` in its result and setting `evidence_use` to `stale_diagnostic_only`.
That evidence cannot support current source, integrated, staging, promotion, or
release claims.
