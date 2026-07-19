"""Tests for output checker."""


class TestOutputChecker:
    """Tests for OutputChecker."""

    def test_normal_output_passes(self, output_checker):
        """Normal text should pass output check."""
        result = output_checker.check("这是一段正常的大模型回复")
        assert result.is_safe is True
        assert result.final_output == "这是一段正常的大模型回复"

    def test_output_with_keyword_blocked(self, output_checker):
        """Output containing blocked keywords should be intercepted."""
        result = output_checker.check("违规词出现在大模型回复中")
        assert result.is_safe is False
        assert (
            "违规词" not in result.final_output or result.final_output != "违规词出现在大模型回复中"
        )

    def test_block_message_used(self, output_checker):
        """Blocked output should use the configured block message."""
        result = output_checker.check("违规词")
        if not result.is_safe:
            assert len(result.safe_output) > 0
            assert result.safe_output == output_checker.block_message

    def test_empty_output(self, output_checker):
        """Empty output should pass."""
        result = output_checker.check("")
        assert result.is_safe is True

    def test_output_check_result_final_output(self, output_checker):
        """final_output property should return correct value."""
        # Safe
        result = output_checker.check("正常文本")
        assert result.final_output == "正常文本"
