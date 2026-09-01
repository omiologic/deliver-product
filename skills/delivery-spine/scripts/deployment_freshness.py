#!/usr/bin/env python3
"""Emit and check environment-qualified deployment freshness receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


IDENTIFIER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ReceiptError(ValueError):
    pass


def identity(value: str) -> dict[str, str]:
    if not SHA256.fullmatch(value):
        raise ReceiptError("identity must be a lowercase SHA-256 value")
    return {"algorithm": "sha256", "value": value}


def validate_endpoint(value: str) -> str:
    if not isinstance(value, str):
        raise ReceiptError("endpoint must be a string")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ReceiptError("endpoint must be an HTTPS URL without credentials, query, or fragment")
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise ReceiptError("endpoint contains forbidden whitespace or control characters")
    return value.rstrip("/")


def validate_identifier(label: str, value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ReceiptError(f"{label} must be a lowercase kebab identifier")
    return value


def validate_receipt_identity(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048 or any(ord(character) < 32 for character in value):
        raise ReceiptError("deployment receipt must be a bounded printable identifier")
    return value


def valid_time(value: str) -> str:
    if not isinstance(value, str):
        raise ReceiptError("observed_at must be RFC 3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReceiptError("observed_at must be RFC 3339") from exc
    if parsed.tzinfo is None:
        raise ReceiptError("observed_at must include a timezone")
    return value


def fingerprint(paths: list[str]) -> str:
    if not paths:
        raise ReceiptError("at least one path is required")
    selected: list[tuple[str, Path]] = []
    common = Path(os.path.commonpath([str(Path(path).resolve()) for path in paths]))
    for raw in paths:
        root = Path(raw).resolve()
        if not root.exists():
            raise ReceiptError(f"selected path does not exist: {raw}")
        if root.is_symlink():
            raise ReceiptError(f"selected path must not be a symlink: {raw}")
        if root.is_file():
            selected.append((root.relative_to(common).as_posix(), root))
            continue
        for child in root.rglob("*"):
            if child.is_symlink():
                raise ReceiptError(f"selected tree contains a symlink: {child}")
            if child.is_file():
                selected.append((child.relative_to(common).as_posix(), child))
    if not selected:
        raise ReceiptError("selected paths contain no files")
    digest = hashlib.sha256()
    for relative, path in sorted(selected):
        digest.update(b"file\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_hash(paths: list[str], supplied: str | None, label: str, *, nullable: bool = False) -> str | None:
    if paths and supplied:
        raise ReceiptError(f"choose {label} paths or a supplied identity, not both")
    if supplied:
        return identity(supplied)["value"]
    if paths:
        return fingerprint(paths)
    if nullable:
        return None
    raise ReceiptError(f"{label} paths or identity are required")


def build_expected(args: argparse.Namespace) -> dict[str, object]:
    return {
        "environment": validate_identifier("environment", args.environment),
        "deployable_unit": validate_identifier("deployable unit", args.deployable_unit),
        "endpoint": validate_endpoint(args.endpoint),
        "artifact_identity": identity(resolve_hash(args.artifact_path, args.artifact_identity, "artifact")),
        "public_configuration_identity": (
            identity(value)
            if (value := resolve_hash(args.public_config_path, args.public_config_identity, "public configuration", nullable=True))
            else None
        ),
        "source_identity": identity(resolve_hash(args.source_path, args.source_identity, "source")),
    }


def validate_receipt(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        raise ReceiptError("receipt must be a JSON object")
    required = {
        "schema_version", "environment", "deployable_unit", "endpoint",
        "artifact_identity", "public_configuration_identity", "source_identity",
        "deployment", "observed_at",
    }
    if set(data) != required:
        missing = sorted(required - set(data))
        extra = sorted(set(data) - required)
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unknown " + ", ".join(extra))
        raise ReceiptError("receipt fields are invalid: " + "; ".join(detail))
    if data["schema_version"] != 1:
        raise ReceiptError("schema_version must be 1")
    validate_identifier("environment", data["environment"])
    validate_identifier("deployable unit", data["deployable_unit"])
    validate_endpoint(data["endpoint"])
    for label in ("artifact_identity", "source_identity"):
        value = data[label]
        if not isinstance(value, dict) or set(value) != {"algorithm", "value"} or value.get("algorithm") != "sha256":
            raise ReceiptError(f"{label} must be a SHA-256 identity")
        identity(value.get("value", ""))
    public = data["public_configuration_identity"]
    if public is not None:
        if not isinstance(public, dict) or set(public) != {"algorithm", "value"} or public.get("algorithm") != "sha256":
            raise ReceiptError("public_configuration_identity must be null or a SHA-256 identity")
        identity(public.get("value", ""))
    deployment = data["deployment"]
    if not isinstance(deployment, dict) or set(deployment) != {"provider", "receipt"}:
        raise ReceiptError("deployment requires only provider and receipt")
    validate_identifier("deployment provider", deployment.get("provider", ""))
    validate_receipt_identity(deployment.get("receipt", ""))
    valid_time(data["observed_at"])
    return data


def write_json(data: dict[str, object], output: str | None) -> None:
    rendered = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if not output:
        sys.stdout.write(rendered)
        return

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    print(f"deployment receipt retained: {target}")


def emit_receipt(args: argparse.Namespace) -> int:
    expected = build_expected(args)
    receipt = {
        "schema_version": 1,
        **expected,
        "deployment": {
            "provider": validate_identifier("deployment provider", args.deployment_provider),
            "receipt": validate_receipt_identity(args.deployment_receipt),
        },
        "observed_at": valid_time(args.observed_at) if args.observed_at else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    validate_receipt(receipt)
    write_json(receipt, args.output)
    return 0


def check_receipt(args: argparse.Namespace) -> int:
    receipt_path = Path(args.receipt)
    if not receipt_path.is_file():
        result = {"state": "UNKNOWN", "evidence_use": "stale_diagnostic_only" if args.stale_diagnostic else "blocked", "reasons": ["receipt_missing"]}
        print(json.dumps(result, sort_keys=True))
        return 0 if args.stale_diagnostic else 2
    try:
        receipt = validate_receipt(json.loads(receipt_path.read_text(encoding="utf-8")))
        expected = build_expected(args)
    except (OSError, json.JSONDecodeError, ReceiptError) as exc:
        result = {"state": "UNKNOWN", "evidence_use": "stale_diagnostic_only" if args.stale_diagnostic else "blocked", "reasons": [str(exc)]}
        print(json.dumps(result, sort_keys=True))
        return 0 if args.stale_diagnostic else 2

    mismatches = [field for field, value in expected.items() if receipt.get(field) != value]
    state = "STALE" if mismatches else "FRESH"
    result = {
        "state": state,
        "environment": expected["environment"],
        "deployable_unit": expected["deployable_unit"],
        "endpoint": expected["endpoint"],
        "evidence_use": "stale_diagnostic_only" if args.stale_diagnostic and state != "FRESH" else ("current_source" if state == "FRESH" else "blocked"),
        "reasons": [f"{field}_mismatch" for field in mismatches],
        "observed_at": receipt["observed_at"],
        "deployment": receipt["deployment"],
    }
    print(json.dumps(result, sort_keys=True))
    if state == "FRESH" or args.stale_diagnostic:
        return 0
    return 1


def add_identity_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--environment", required=True)
    parser.add_argument("--deployable-unit", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--artifact-path", action="append", default=[])
    parser.add_argument("--artifact-identity")
    parser.add_argument("--public-config-path", action="append", default=[])
    parser.add_argument("--public-config-identity")
    parser.add_argument("--source-path", action="append", default=[])
    parser.add_argument("--source-identity")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    emit_parser = subparsers.add_parser("emit")
    add_identity_arguments(emit_parser)
    emit_parser.add_argument("--deployment-provider", required=True)
    emit_parser.add_argument("--deployment-receipt", required=True)
    emit_parser.add_argument("--observed-at")
    emit_parser.add_argument("--output")
    emit_parser.set_defaults(handler=emit_receipt)

    check_parser = subparsers.add_parser("check")
    add_identity_arguments(check_parser)
    check_parser.add_argument("--receipt", required=True)
    check_parser.add_argument("--stale-diagnostic", action="store_true")
    check_parser.set_defaults(handler=check_receipt)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except ReceiptError as exc:
        print(f"deployment freshness evidence is UNKNOWN: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
