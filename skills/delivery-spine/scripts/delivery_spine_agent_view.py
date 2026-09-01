#!/usr/bin/env python3
"""Render lossless, benchmark-gated Delivery Spine agent-input views."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


POLICY_PATH = Path(__file__).parents[1] / "references" / "agent-view-selection-policy.json"
AGENT_VIEW_VERSION = 1
COMPACT_JSON_VERSION = "RFC8259"
HEADER_ROWS_VERSION = "1"
TOON_VERSION = "4.1"
SAFE_YAML_PROFILE = "delivery-spine-safe-yaml-1.2-v1"
FORMATS = ("compact-json", "toon", "safe-yaml", "auto")
INTERNAL_CANDIDATES = ("compact-json", "header-json", "toon", "safe-yaml", "header-json-aliases")
PROPERTY_ALIASES = {
    "journey_id": "j",
    "work_item_id": "w",
    "target_level": "t",
    "current_level": "c",
    "observed_at": "o",
    "affected_paths": "p",
    "reference": "r",
    "boundaries": "b",
    "evidence": "e",
}


class AgentViewError(ValueError):
    """Raised when a candidate cannot be encoded or reconstructed safely."""


@dataclass(frozen=True)
class RenderedView:
    text: str
    encoding: str
    requested_encoding: str
    estimated_token_count: int | None
    fallback_reason: str | None


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise AgentViewError("selection policy must be a schema-version 1 object")
    return value


def _distribution_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        raise AgentViewError(f"required implementation is unavailable: {distribution}") from exc


def policy_token_counter(policy: dict[str, Any]) -> tuple[Callable[[str], int], dict[str, str]]:
    configured = policy["tokenizer"]
    if configured.get("implementation") != "tiktoken":
        raise AgentViewError("selection policy tokenizer implementation is unsupported")
    installed = _distribution_version("tiktoken")
    if installed != configured.get("version"):
        raise AgentViewError(
            f"tokenizer version is unapproved: expected {configured.get('version')}, found {installed}"
        )
    tiktoken = importlib.import_module("tiktoken")
    encoding_name = configured["encoding"]
    encoding = tiktoken.get_encoding(encoding_name)
    return lambda text: len(encoding.encode(text)), {
        "implementation": "tiktoken",
        "version": installed,
        "encoding": encoding_name,
    }


def _header_rows_encode(value: Any) -> Any:
    if isinstance(value, list):
        rows = [_header_rows_encode(item) for item in value]
        if rows and all(isinstance(row, dict) for row in rows):
            fields = list(rows[0])
            if fields and all(list(row) == fields for row in rows):
                return {
                    "$delivery_spine_rows": HEADER_ROWS_VERSION,
                    "fields": fields,
                    "rows": [[row[field] for field in fields] for row in rows],
                }
        return rows
    if isinstance(value, dict):
        return {key: _header_rows_encode(item) for key, item in value.items()}
    return value


def _header_rows_decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_header_rows_decode(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"$delivery_spine_rows", "fields", "rows"}:
            if value["$delivery_spine_rows"] != HEADER_ROWS_VERSION:
                raise AgentViewError("header-plus-rows version is unsupported")
            fields = value["fields"]
            rows = value["rows"]
            if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
                raise AgentViewError("header-plus-rows fields are invalid")
            if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != len(fields) for row in rows):
                raise AgentViewError("header-plus-rows row width is invalid")
            return [
                {field: _header_rows_decode(item) for field, item in zip(fields, row)}
                for row in rows
            ]
        return {key: _header_rows_decode(item) for key, item in value.items()}
    return value


def _alias_encode(value: Any, aliases: dict[str, str]) -> Any:
    if isinstance(value, list):
        return [_alias_encode(item, aliases) for item in value]
    if isinstance(value, dict):
        return {aliases.get(key, key): _alias_encode(item, aliases) for key, item in value.items()}
    return value


def _alias_decode(value: Any, aliases: dict[str, str]) -> Any:
    reverse = {alias: field for field, alias in aliases.items()}
    if isinstance(value, list):
        return [_alias_decode(item, aliases) for item in value]
    if isinstance(value, dict):
        return {reverse.get(key, key): _alias_decode(item, aliases) for key, item in value.items()}
    return value


def _aliased_header_encode(value: Any) -> str:
    wrapped = {
        "$delivery_spine_aliases": PROPERTY_ALIASES,
        "value": _header_rows_encode(_alias_encode(value, PROPERTY_ALIASES)),
    }
    return compact_json(wrapped)


def _aliased_header_decode(text: str) -> Any:
    wrapped = json.loads(text)
    if not isinstance(wrapped, dict) or set(wrapped) != {"$delivery_spine_aliases", "value"}:
        raise AgentViewError("property-alias wrapper is invalid")
    if wrapped["$delivery_spine_aliases"] != PROPERTY_ALIASES:
        raise AgentViewError("property-alias dictionary is unapproved")
    return _alias_decode(_header_rows_decode(wrapped["value"]), PROPERTY_ALIASES)


def _toon_codec() -> tuple[Callable[[Any], str], Callable[[str], Any], str]:
    installed = _distribution_version("toon-format")
    module = importlib.import_module("toon_format")
    encode = getattr(module, "encode", None)
    decode = getattr(module, "decode", None)
    if not callable(encode) or not callable(decode):
        raise AgentViewError("toon-format implementation lacks encode/decode")
    options = getattr(module, "DecodeOptions", None)
    if options is None:
        raise AgentViewError("toon-format implementation lacks strict decode options")
    return encode, lambda text: decode(text, options(strict=True)), installed


def _yaml_codec() -> tuple[Callable[[Any], str], Callable[[str], Any], str]:
    installed = _distribution_version("PyYAML")
    yaml = importlib.import_module("yaml")
    tokens = importlib.import_module("yaml.tokens")
    nodes = importlib.import_module("yaml.nodes")

    class RestrictedLoader(yaml.SafeLoader):
        def construct_mapping(self, node: Any, deep: bool = False) -> dict[str, Any]:
            if not isinstance(node, nodes.MappingNode):
                raise AgentViewError("restricted YAML mapping node is invalid")
            pairs: list[tuple[str, Any]] = []
            seen: set[str] = set()
            for key_node, value_node in node.value:
                if key_node.tag != "tag:yaml.org,2002:str":
                    raise AgentViewError("restricted YAML permits only string mapping keys")
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str):
                    raise AgentViewError("restricted YAML permits only string mapping keys")
                if key in seen:
                    raise AgentViewError(f"restricted YAML duplicate mapping key: {key}")
                seen.add(key)
                pairs.append((key, self.construct_object(value_node, deep=deep)))
            return dict(pairs)

    class RestrictedDumper(yaml.SafeDumper):
        def ignore_aliases(self, data: Any) -> bool:
            return True

    def reject_unsafe_syntax(text: str) -> None:
        forbidden = (tokens.AliasToken, tokens.AnchorToken, tokens.TagToken, tokens.DirectiveToken)
        for token in yaml.scan(text):
            if isinstance(token, forbidden):
                raise AgentViewError("restricted YAML prohibits aliases, anchors, and custom tags")

    def encode(value: Any) -> str:
        return yaml.dump(
            value,
            Dumper=RestrictedDumper,
            allow_unicode=True,
            default_flow_style=False,
            explicit_start=False,
            sort_keys=True,
        )

    def decode(text: str) -> Any:
        reject_unsafe_syntax(text)
        return yaml.load(text, Loader=RestrictedLoader)

    return encode, decode, installed


def _codec(candidate: str) -> tuple[Callable[[Any], str], Callable[[str], Any], dict[str, str]]:
    if candidate == "compact-json":
        return compact_json, json.loads, {"implementation": "python-json", "version": sys.version.split()[0]}
    if candidate == "header-json":
        return (
            lambda value: compact_json(_header_rows_encode(value)),
            lambda text: _header_rows_decode(json.loads(text)),
            {"implementation": "delivery-spine-header-rows", "version": HEADER_ROWS_VERSION},
        )
    if candidate == "header-json-aliases":
        return (
            _aliased_header_encode,
            _aliased_header_decode,
            {"implementation": "delivery-spine-header-rows-aliases", "version": "1"},
        )
    if candidate == "toon":
        encode, decode, installed = _toon_codec()
        return encode, decode, {"implementation": "toon-format", "version": installed}
    if candidate == "safe-yaml":
        encode, decode, installed = _yaml_codec()
        return encode, decode, {"implementation": "PyYAML-restricted", "version": installed}
    raise AgentViewError(f"unsupported agent-view candidate: {candidate}")


def _encoding_version(candidate: str) -> str:
    return {
        "compact-json": COMPACT_JSON_VERSION,
        "header-json": HEADER_ROWS_VERSION,
        "toon": TOON_VERSION,
        "safe-yaml": SAFE_YAML_PROFILE,
        "header-json-aliases": "1",
    }[candidate]


def _envelope(
    data: Any,
    candidate: str,
    requested: str,
    policy: dict[str, Any],
    tokenizer: dict[str, str] | None,
    implementation: dict[str, str],
    token_count: int | None,
    fallback_reason: str | None,
) -> dict[str, Any]:
    return {
        "agent_view": {
            "version": AGENT_VIEW_VERSION,
            "encoding": candidate,
            "encoding_version": _encoding_version(candidate),
            "requested_encoding": requested,
            "selection_policy": {
                "version": policy["policy_version"],
                "provenance": policy["provenance"],
            },
            "tokenizer": tokenizer,
            "estimated_token_count": token_count,
            "implementation": implementation,
            "complete": True,
            "fallback_reason": fallback_reason,
        },
        "data": data,
    }


def render_candidate(
    data: Any,
    candidate: str,
    requested: str,
    policy: dict[str, Any],
    *,
    token_counter: Callable[[str], int] | None,
    tokenizer: dict[str, str] | None,
    fallback_reason: str | None = None,
) -> RenderedView:
    encode, decode, implementation = _codec(candidate)
    approved_implementation = policy.get("candidate_implementations", {}).get(candidate)
    if candidate in ("toon", "safe-yaml") and implementation != approved_implementation:
        raise AgentViewError(
            f"{candidate} implementation is unapproved: expected {approved_implementation}, found {implementation}"
        )
    approved_version = policy.get("candidate_versions", {}).get(candidate)
    if approved_version != _encoding_version(candidate):
        raise AgentViewError(
            f"{candidate} format/profile version is unapproved: expected {approved_version}, found {_encoding_version(candidate)}"
        )
    count: int | None = None
    text = ""
    for _ in range(8):
        envelope = _envelope(data, candidate, requested, policy, tokenizer, implementation, count, fallback_reason)
        text = encode(envelope)
        reconstructed = decode(text)
        if not isinstance(reconstructed, dict) or reconstructed.get("data") != data:
            raise AgentViewError(f"{candidate} failed lossless reconstruction")
        updated = token_counter(text) if token_counter else None
        if updated == count:
            break
        count = updated
    else:
        raise AgentViewError(f"{candidate} token count did not stabilize")
    return RenderedView(text, candidate, requested, count, fallback_reason)


def _compact_fallback(
    data: Any,
    requested: str,
    policy: dict[str, Any],
    reason: str,
    token_counter: Callable[[str], int] | None,
    tokenizer: dict[str, str] | None,
) -> RenderedView:
    return render_candidate(
        data,
        "compact-json",
        requested,
        policy,
        token_counter=token_counter,
        tokenizer=tokenizer,
        fallback_reason=reason,
    )


def render_agent_view(
    data: Any,
    requested: str = "compact-json",
    *,
    policy: dict[str, Any] | None = None,
    token_counter: Callable[[str], int] | None = None,
    tokenizer: dict[str, str] | None = None,
) -> RenderedView:
    if requested not in FORMATS:
        raise AgentViewError(f"unsupported requested encoding: {requested}")
    selected_policy = policy or load_policy()
    if token_counter is None and tokenizer is None:
        try:
            token_counter, tokenizer = policy_token_counter(selected_policy)
        except AgentViewError as exc:
            if requested != "compact-json":
                return _compact_fallback(data, requested, selected_policy, str(exc), None, None)

    if requested == "compact-json":
        return render_candidate(
            data,
            requested,
            requested,
            selected_policy,
            token_counter=token_counter,
            tokenizer=tokenizer,
        )

    if requested in ("toon", "safe-yaml"):
        try:
            return render_candidate(
                data,
                requested,
                requested,
                selected_policy,
                token_counter=token_counter,
                tokenizer=tokenizer,
            )
        except (AgentViewError, TypeError, ValueError) as exc:
            return _compact_fallback(data, requested, selected_policy, str(exc), token_counter, tokenizer)

    if token_counter is None:
        return _compact_fallback(
            data, requested, selected_policy, "approved tokenizer is unavailable", None, tokenizer
        )
    try:
        baseline = render_candidate(
            data,
            "compact-json",
            requested,
            selected_policy,
            token_counter=token_counter,
            tokenizer=tokenizer,
        )
    except (AgentViewError, TypeError, ValueError) as exc:
        raise AgentViewError(f"compact JSON fallback failed: {exc}") from exc
    if baseline.estimated_token_count is None:
        return baseline

    thresholds = selected_policy["thresholds"]
    candidates: list[RenderedView] = []
    for candidate in selected_policy.get("approved_candidates", []):
        if candidate == "compact-json":
            continue
        try:
            rendered = render_candidate(
                data,
                candidate,
                requested,
                selected_policy,
                token_counter=token_counter,
                tokenizer=tokenizer,
            )
        except (AgentViewError, TypeError, ValueError):
            continue
        saved = baseline.estimated_token_count - (rendered.estimated_token_count or baseline.estimated_token_count)
        percent = 100 * saved / baseline.estimated_token_count
        if saved >= thresholds["absolute_floor_tokens"] and percent >= thresholds["minimum_percent"]:
            candidates.append(rendered)
    if not candidates:
        return baseline
    order = {name: index for index, name in enumerate(selected_policy["tie_break_order"])}
    return min(candidates, key=lambda item: (item.estimated_token_count or math.inf, order[item.encoding]))


def decode_agent_view(text: str, encoding: str) -> dict[str, Any]:
    _, decode, _ = _codec(encoding)
    value = decode(text)
    if not isinstance(value, dict) or set(value) != {"agent_view", "data"}:
        raise AgentViewError("agent view envelope is invalid")
    return value
