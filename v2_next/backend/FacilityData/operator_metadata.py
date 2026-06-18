from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from backend import config
from backend.FacilityData.schemas import OperatorMetadata, OperatorMetadataHistoryEntry, OperatorMetadataUpdate


OPERATOR_METADATA_VERSION = "1.0.0"
OPERATOR_METADATA_HISTORY_LIMIT = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class OperatorMetadataStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (config.APP_DATA_DIR / "operator_metadata.json")
        self._lock = threading.Lock()
        self._logger = logging.getLogger("SmartFactoryLoggerV2")
        self._metadata = OperatorMetadata()
        self._load()

    def get(self) -> OperatorMetadata:
        with self._lock:
            return self._metadata.model_copy(deep=True)

    def update(self, payload: OperatorMetadataUpdate) -> OperatorMetadata:
        with self._lock:
            history = self._build_history_locked(
                previous=self._metadata,
                next_product_no=payload.product_no,
                next_operator_mold_no=payload.operator_mold_no,
            )
            next_metadata = OperatorMetadata(
                product_no=payload.product_no,
                operator_mold_no=payload.operator_mold_no,
                updated_at=_utc_now_iso(),
                source="operator_input",
                history=history,
            )
            self._persist_locked(next_metadata)
            self._metadata = next_metadata
            return self._metadata.model_copy(deep=True)

    def reset(self) -> OperatorMetadata:
        with self._lock:
            next_metadata = OperatorMetadata(
                product_no="",
                operator_mold_no="",
                updated_at=_utc_now_iso(),
                source="operator_input",
                history=self._build_history_locked(
                    previous=self._metadata,
                    next_product_no="",
                    next_operator_mold_no="",
                ),
            )
            self._persist_locked(next_metadata)
            self._metadata = next_metadata
            return self._metadata.model_copy(deep=True)

    def _load(self) -> None:
        try:
            if not self._path.exists():
                return
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            data = raw.get("metadata", raw)
            self._metadata = OperatorMetadata(**data)
        except Exception as exc:
            self._logger.warning("Operator metadata load failed: %s", exc)
            self._metadata = OperatorMetadata()

    def _build_history_locked(
        self,
        previous: OperatorMetadata,
        next_product_no: str,
        next_operator_mold_no: str,
    ) -> list[OperatorMetadataHistoryEntry]:
        history = list(previous.history)
        previous_is_valid = bool(previous.valid and previous.product_no and previous.operator_mold_no)
        same_as_next = (
            previous.product_no == next_product_no and
            previous.operator_mold_no == next_operator_mold_no
        )

        if previous_is_valid and not same_as_next:
            history.insert(
                0,
                OperatorMetadataHistoryEntry(
                    product_no=previous.product_no,
                    operator_mold_no=previous.operator_mold_no,
                    updated_at=previous.updated_at,
                ),
            )

        deduped: list[OperatorMetadataHistoryEntry] = []
        seen: set[tuple[str, str]] = set()
        for item in history:
            key = (item.product_no, item.operator_mold_no)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= OPERATOR_METADATA_HISTORY_LIMIT:
                break
        return deduped

    def _persist_locked(self, metadata: OperatorMetadata) -> None:
        payload = {
            "operator_metadata_version": OPERATOR_METADATA_VERSION,
            "metadata": metadata.model_dump(),
        }
        temp_path = self._path.with_name(f"{self._path.name}.tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(self._path)
        except Exception as exc:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            self._logger.error("Operator metadata persist failed: %s", exc)
            raise


operator_metadata_store = OperatorMetadataStore()
