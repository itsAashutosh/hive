"""
Tests for CheckpointStore exception handling and pruning logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from framework.storage.checkpoint_store import CheckpointStore

# A dummy index and checkpoint model since we're just testing the parsing loop
class MockCheckpoint:
    def __init__(self, checkpoint_id: str, created_at: str):
        self.checkpoint_id = checkpoint_id
        self.created_at = created_at

class MockIndex:
    def __init__(self, checkpoints: list[MockCheckpoint]):
        self.checkpoints = checkpoints


class TestCheckpointStorePrune:

    @pytest.mark.asyncio
    async def test_prune_handles_bad_timestamps_gracefully(self, caplog):
        """Test that invalid timestamps raise ValueError/TypeError and are logged."""
        store = CheckpointStore("dummy_path")
        
        # Valid old checkpoint, valid recent checkpoint, invalid format, invalid type
        old_time = (datetime.now() - timedelta(days=5)).isoformat()
        recent_time = (datetime.now() - timedelta(hours=1)).isoformat()
        
        index = MockIndex(
            checkpoints=[
                MockCheckpoint("old_cp", old_time),
                MockCheckpoint("recent_cp", recent_time),
                MockCheckpoint("bad_format", "not-a-timestamp"),
                # Note: created_at typing is usually str, but testing type error resilience
                MockCheckpoint("bad_type", None), 
            ]
        )
        
        store.load_index = AsyncMock(return_value=index)
        store.delete_checkpoint = AsyncMock(return_value=True)

        with caplog.at_level(logging.WARNING):
            deleted = await store.prune_checkpoints(max_age_days=3)
            
        assert deleted == 1  # Only old_cp deleted
        
        # Verify log formatting does not use f-strings and works properly
        log_messages = [r.message for r in caplog.records]
        assert any("Failed to parse timestamp for bad_format" in m for m in log_messages)
        assert any("Failed to parse timestamp for bad_type" in m for m in log_messages)
        
        store.delete_checkpoint.assert_called_once_with("old_cp")
