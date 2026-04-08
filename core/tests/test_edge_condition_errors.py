"""
Tests for EdgeSpec condition evaluation error handling.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

from framework.graph.edge import EdgeCondition, EdgeSpec


class TestEdgeConditionEvalErrorHandling:

    def test_evaluate_condition_catches_eval_errors(self, caplog):
        """Test that syntax errors in condition expressions are caught and logged at ERROR level."""
        edge = EdgeSpec(
            id="test_edge",
            source="node_a",
            target="node_b",
            condition=EdgeCondition.CONDITIONAL,
            condition_expr="invalid syntax !!",
        )

        with caplog.at_level(logging.ERROR):
            result = edge._evaluate_condition({}, {})

        assert result is False
        assert any("Condition evaluation failed for edge test_edge" in r.message for r in caplog.records)

    def test_evaluate_condition_lets_interrupts_propagate(self):
        """Test that KeyboardInterrupt propagates up."""
        edge = EdgeSpec(
            id="test_edge",
            source="node_a",
            target="node_b",
            condition=EdgeCondition.CONDITIONAL,
            condition_expr="output.val",
        )

        with patch("framework.graph.edge.safe_eval", side_effect=KeyboardInterrupt):
            try:
                edge._evaluate_condition({}, {})
                assert False, "Should have raised KeyboardInterrupt"
            except KeyboardInterrupt:
                pass
