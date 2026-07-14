#!/usr/bin/env python3
"""CLI Demo — 命令行演示入口，展示完整风控链路。

Usage:
    python demo/cli_demo.py              # 运行所有预设场景
    python demo/cli_demo.py --interactive  # 交互模式
    python demo/cli_demo.py --scenario 0   # 运行指定场景
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.normalizer import TextNormalizer, NormalizerConfig
from src.detection.rule_detector import RuleDetector
from src.detection.semantic_detector import SemanticDetector
from src.rules.repository import RuleRepository
from src.rules.manager import RuleManager
from src.decision.fusion import RiskFusion
from src.desensitization.desensitizer import Desensitizer, DesensitizeConfig
from src.output_check.checker import OutputChecker
from src.audit.logger import AuditLogger, AuditRecord
from src.llm.client import LLMClient, LLMConfig
from demo.scenarios import SCENARIOS, DemoScenario


# =============================================================================
# Colors for terminal output
# =============================================================================

class Color:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{Color.BOLD}{Color.BLUE}{'='*60}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}  {title}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}{'='*60}{Color.RESET}")


def print_result(label: str, value: str, color: str = Color.RESET) -> None:
    """Print a labeled result line."""
    print(f"  {Color.BOLD}{label}:{Color.RESET} {color}{value}{Color.RESET}")


def run_pipeline(text: str, scenario_name: str,
                 normalizer: TextNormalizer,
                 rule_detector: RuleDetector,
                 semantic_detector: SemanticDetector,
                 fusion: RiskFusion,
                 desensitizer: Desensitizer,
                 output_checker: OutputChecker,
                 audit_logger: AuditLogger,
                 llm_client: LLMClient | None = None) -> AuditRecord:
    """Run the full content filtering pipeline on a single input."""
    record = AuditRecord(original_input=text)
    start_time = time.time()

    # Step 1: Normalize
    normalized = normalizer.normalize(text)
    record.normalized_input = normalized.normalized

    # Step 2: Rule detection
    rule_evidence = rule_detector.detect(normalized.normalized)

    # Step 3: Semantic detection (only if rules are uncertain or missed)
    semantic_evidence = semantic_detector.detect(normalized.normalized)

    # Step 4: Risk fusion
    risk_result = fusion.evaluate_input(rule_evidence, semantic_evidence)
    record.input_risk_level = risk_result.risk_level.value
    record.input_risk_category = risk_result.risk_category.value if risk_result.risk_category else None
    record.input_confidence = risk_result.confidence
    record.input_action = risk_result.action
    record.input_evidence = [
        {"source": e.source.value, "category": e.category.value if e.category else "",
         "confidence": e.confidence, "explanation": e.explanation}
        for e in risk_result.evidence_chain
    ]

    # Step 5: Act on risk level
    if risk_result.risk_level.value == "high":
        # Block directly
        record.final_output = "抱歉，您的请求包含不适宜内容，无法处理。"
        record.total_duration_ms = (time.time() - start_time) * 1000
        audit_logger.log(record)
        return record

    elif risk_result.risk_level.value == "medium":
        # Desensitize (with LLM rewrite if mode="rewrite")
        llm_rewrite = None
        if desensitizer.config.mode == "rewrite" and llm_client:
            def _rewrite(prompt: str) -> str:
                resp = llm_client.chat(prompt)
                return resp.text if resp.success else ""
            llm_rewrite = _rewrite
        des_result = desensitizer.desensitize(text, risk_result, llm_call=llm_rewrite)
        safe_input = des_result.desensitized
        record.desensitized_input = safe_input
    else:
        safe_input = text

    # Step 6: Call LLM (if available)
    if llm_client:
        llm_resp = llm_client.chat(safe_input)
        record.llm_called = True
        record.llm_model = llm_client.config.model
        if llm_resp.success:
            llm_output = llm_resp.text
        else:
            llm_output = f"[LLM Error: {llm_resp.error}]"
    else:
        # Simulate LLM response for demo
        llm_output = f'[模拟大模型回复] 针对您的问题“{text[:30]}”，这是一个示例回答。'
        record.llm_called = False
        record.llm_model = "demo-simulation"

    record.llm_output = llm_output

    # Step 7: Output re-check
    output_result = output_checker.check(llm_output)
    record.output_risk_level = output_result.risk_result.risk_level.value if output_result.risk_result else "low"
    record.output_passed = output_result.is_safe
    record.output_blocked = not output_result.is_safe
    record.final_output = output_result.final_output

    record.total_duration_ms = (time.time() - start_time) * 1000
    audit_logger.log(record)
    return record


def print_pipeline_result(record: AuditRecord) -> None:
    """Pretty-print pipeline result."""
    # Input
    print(f"\n  {Color.CYAN}📥 原始输入:{Color.RESET} {record.original_input[:80]}")
    if record.normalized_input != record.original_input:
        print(f"  {Color.CYAN}🔧 规范化后:{Color.RESET} {record.normalized_input[:80]}")

    # Risk assessment
    level_color = {
        "high": Color.RED,
        "medium": Color.YELLOW,
        "low": Color.GREEN,
    }.get(record.input_risk_level, Color.RESET)

    print(f"  {Color.CYAN}🎯 风险等级:{Color.RESET} {level_color}{record.input_risk_level.upper()}{Color.RESET}", end="")
    if record.input_risk_category:
        print(f" | 类别: {record.input_risk_category} | 置信度: {record.input_confidence:.2f}")
    else:
        print()

    # Action
    action_icons = {"block": "🛑", "desensitize": "⚠️", "pass": "✅"}
    action_icon = action_icons.get(record.input_action, "❓")
    print(f"  {Color.CYAN}🔀 处置动作:{Color.RESET} {action_icon} {record.input_action}")

    # Evidence
    if record.input_evidence:
        print(f"  {Color.CYAN}📋 命中证据:{Color.RESET}")
        for ev in record.input_evidence:
            print(f"      - [{ev['source']}] {ev['explanation']}")

    # Desensitization
    if record.desensitized_input:
        print(f"  {Color.CYAN}🔒 脱敏结果:{Color.RESET} {record.desensitized_input[:80]}")

    # LLM
    if record.llm_called:
        print(f"  {Color.CYAN}🤖 LLM 调用:{Color.RESET} {record.llm_model}")
        print(f"  {Color.CYAN}💬 LLM 输出:{Color.RESET} {record.llm_output[:80]}")

    # Output check
    if record.output_passed:
        print(f"  {Color.CYAN}🔁 输出复检:{Color.RESET} {Color.GREEN}✅ 通过{Color.RESET}")
    else:
        print(f"  {Color.CYAN}🔁 输出复检:{Color.RESET} {Color.RED}🛑 拦截{Color.RESET}")

    # Final
    print(f"  {Color.CYAN}📤 最终输出:{Color.RESET} {record.final_output[:80]}")
    print(f"  {Color.CYAN}⏱️ 耗时:{Color.RESET} {record.total_duration_ms:.1f}ms")


def run_all_scenarios(normalizer, rule_detector, semantic_detector,
                      fusion, desensitizer, output_checker,
                      audit_logger, llm_client) -> None:
    """Run all predefined demo scenarios."""
    print_header("🚀 预设场景演示")
    print(f"共 {len(SCENARIOS)} 个场景\n")

    for i, scenario in enumerate(SCENARIOS):
        print(f"\n{Color.BOLD}── 场景 {i+1}: {scenario.name} ──{Color.RESET}")
        print(f"  {Color.CYAN}目的:{Color.RESET} {scenario.display_purpose}")
        print(f"  {Color.CYAN}描述:{Color.RESET} {scenario.description}")

        record = run_pipeline(
            scenario.input_text, scenario.name,
            normalizer, rule_detector, semantic_detector,
            fusion, desensitizer, output_checker,
            audit_logger, llm_client,
        )
        print_pipeline_result(record)

    print_header("✅ 演示完成")


def run_interactive(normalizer, rule_detector, semantic_detector,
                    fusion, desensitizer, output_checker,
                    audit_logger, llm_client) -> None:
    """Interactive mode — user types input and sees real-time results."""
    print_header("💬 交互模式")
    print("输入文本查看风控结果，输入 'quit' 退出\n")

    while True:
        try:
            user_input = input(f"{Color.BOLD}你> {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        record = run_pipeline(
            user_input, "interactive",
            normalizer, rule_detector, semantic_detector,
            fusion, desensitizer, output_checker,
            audit_logger, llm_client,
        )
        print_pipeline_result(record)


def main():
    """Main entry point."""
    import argparse

    # 确保 Windows 控制台使用 UTF-8 编码，支持 emoji 输出
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="LLM Dialog Risk Filter — CLI Demo"
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="交互模式"
    )
    parser.add_argument(
        "--scenario", "-s", type=int, default=None,
        help="运行指定场景（0-based 索引）"
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="不连接 LLM，使用模拟回复"
    )
    parser.add_argument(
        "--load-model", action="store_true",
        help="加载语义模型（默认不加载，使用纯规则模式）"
    )
    args = parser.parse_args()

    # ---- Initialize components ----
    print_header("🛡️ LLM 对话内容风控系统 v0.1.0")
    print("初始化组件...")

    # Config
    import yaml
    config_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 从环境变量注入敏感密钥
    # 优先从 .env 文件加载，其次从系统环境变量
    import os as _os
    _env_file = Path(__file__).resolve().parent.parent / ".env"
    if _env_file.exists():
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _key, _val = _line.split("=", 1)
                    _os.environ.setdefault(_key.strip(), _val.strip())
    if _os.environ.get("DEEPSEEK_API_KEY"):
        config["llm"]["api_key"] = _os.environ["DEEPSEEK_API_KEY"]
    if _os.environ.get("SILICONFLOW_API_KEY"):
        config.setdefault("semantic_detection", {}).setdefault("api", {})
        config["semantic_detection"]["api"]["api_key"] = _os.environ["SILICONFLOW_API_KEY"]

    # Normalizer
    bypass_map: dict[str, str] = {}
    bypass_path = Path(__file__).resolve().parent.parent / "config" / "bypass_variants.yaml"
    if bypass_path.exists():
        with open(bypass_path, "r", encoding="utf-8") as f:
            bypass_map = yaml.safe_load(f) or {}

    confusable_map: dict[str, str] = {}
    confusable_path = Path(__file__).resolve().parent.parent / "config" / "confusable_chars.yaml"
    if confusable_path.exists():
        with open(confusable_path, "r", encoding="utf-8") as f:
            confusable_map = yaml.safe_load(f) or {}

    pinyin_map: dict[str, str] = {}
    pinyin_path = Path(__file__).resolve().parent.parent / "config" / "pinyin_variants.yaml"
    if pinyin_path.exists():
        with open(pinyin_path, "r", encoding="utf-8") as f:
            pinyin_map = yaml.safe_load(f) or {}

    traditional_simplified_map: dict[str, str] = {}
    ts_path = Path(__file__).resolve().parent.parent / "config" / "traditional_simplified.yaml"
    if ts_path.exists():
        with open(ts_path, "r", encoding="utf-8") as f:
            traditional_simplified_map = yaml.safe_load(f) or {}

    abbreviation_map: dict[str, str] = {}
    abbr_path = Path(__file__).resolve().parent.parent / "config" / "abbreviation_map.yaml"
    if abbr_path.exists():
        with open(abbr_path, "r", encoding="utf-8") as f:
            abbreviation_map = yaml.safe_load(f) or {}

    decomposition_map: dict[str, str] = {}
    decomp_path = Path(__file__).resolve().parent.parent / "config" / "decomposition_map.yaml"
    if decomp_path.exists():
        with open(decomp_path, "r", encoding="utf-8") as f:
            decomposition_map = yaml.safe_load(f) or {}

    normalizer = TextNormalizer(NormalizerConfig(
        bypass_map=bypass_map,
        confusable_map=confusable_map,
        pinyin_map=pinyin_map,
        traditional_simplified_map=traditional_simplified_map,
        abbreviation_map=abbreviation_map,
        decomposition_map=decomposition_map,
    ))

    # Rules
    rules_dir = Path(__file__).resolve().parent.parent / config["rule_detection"]["rules_dir"]
    repo = RuleRepository(str(rules_dir))
    manager = RuleManager(repo)
    rule_detector = RuleDetector(manager)

    # Semantic
    sem_cfg = config["semantic_detection"]
    api_mode = sem_cfg.get("mode", "local") == "api"
    semantic_detector = SemanticDetector(
        model_name=sem_cfg.get("model_name", "BAAI/bge-small-zh-v1.5"),
        confidence_threshold=sem_cfg["confidence_threshold"],
        device=sem_cfg.get("device", "cpu"),
        category_references=sem_cfg.get("category_references"),
        api_mode=api_mode,
        api_config=sem_cfg.get("api") if api_mode else None,
    )

    # Try to load semantic model if requested
    if args.load_model:
        try:
            print("  加载语义模型...")
            # 国内网络环境使用 HuggingFace 镜像加速
            import os as _os
            if not _os.environ.get("HF_ENDPOINT"):
                _os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            semantic_detector.load_model()
            print(f"  语义模型: {sem_cfg['model_name']} [OK]")
        except Exception as e:
            print(f"  语义模型加载失败: {e}")
            print("  将回退到纯规则模式")

    # Fusion
    fusion_cfg = config["risk_fusion"]
    fusion = RiskFusion()

    # Desensitizer
    ds_cfg = config.get("desensitization", {})
    desensitizer = Desensitizer(DesensitizeConfig(
        mode=ds_cfg.get("mode", "semantic"),
        replacement_char=ds_cfg.get("replacement_char", "*"),
        keep_first_last=ds_cfg.get("keep_first_last", True),
        category_labels=ds_cfg.get("category_labels", {}),
        fallback_label=ds_cfg.get("fallback_label", "[违规内容]"),
        rewrite_prompt=ds_cfg.get("rewrite_prompt", ""),
    ))

    # Output checker
    output_checker = OutputChecker(
        rule_detector, semantic_detector, fusion,
        block_message=config["output_check"]["output_block_message"],
        desensitizer=desensitizer,
    )

    # Audit logger
    audit_cfg = config["audit"]
    audit_logger = AuditLogger(
        log_dir=str(Path(__file__).resolve().parent.parent / audit_cfg["log_dir"]),
    )

    # LLM client
    llm_client = None
    if not args.no_llm:
        llm_cfg = config["llm"]
        llm_client = LLMClient(LLMConfig(
            provider=llm_cfg["provider"],
            base_url=llm_cfg["base_url"],
            model=llm_cfg["model"],
            api_key=llm_cfg["api_key"],
            timeout=llm_cfg["timeout"],
            max_tokens=llm_cfg["max_tokens"],
        ))
        print(f"  LLM: {llm_cfg['provider']} / {llm_cfg['model']}")
    else:
        print("  LLM: 模拟模式")

    print(f"  规则: {sum(1 for r in manager.get_enabled_rules())} 条已启用")
    print("  初始化完成 [OK]\n")

    # ---- Run ----
    if args.interactive:
        run_interactive(
            normalizer, rule_detector, semantic_detector,
            fusion, desensitizer, output_checker,
            audit_logger, llm_client,
        )
    elif args.scenario is not None:
        scenario = SCENARIOS[args.scenario]
        print(f"{Color.BOLD}── 场景 {args.scenario}: {scenario.name} ──{Color.RESET}")
        record = run_pipeline(
            scenario.input_text, scenario.name,
            normalizer, rule_detector, semantic_detector,
            fusion, desensitizer, output_checker,
            audit_logger, llm_client,
        )
        print_pipeline_result(record)
    else:
        run_all_scenarios(
            normalizer, rule_detector, semantic_detector,
            fusion, desensitizer, output_checker,
            audit_logger, llm_client,
        )

    if llm_client:
        llm_client.close()


if __name__ == "__main__":
    main()