#!/usr/bin/env python3
"""
SEQUEL2SQL Benchmark - Main Orchestrator

Runs the complete benchmark pipeline:
1. Display UI and get user confirmation
2. Generate prompts from dataset
3. Run LLM inference with key rotation
4. Post-process to extract SQL
5. Setup Docker containers
6. Run evaluation
7. Display results
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add benchmark/src to path so benchmark modules are importable as 'src.*'
# (benchmark/src is loaded as the 'src' package from CWD=benchmark/)
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.api_client import LLMClient
from src.checkpoint_manager import CheckpointManager
from src.config import (
    DEFAULT_PROVIDER,
    PROVIDERS,
    get_benchmark_dir,
    get_data_dir,
    get_model_config,
    get_outputs_dir,
    load_api_key,
    validate_config,
)
from src.inference_engine import InferenceEngine
from src.logger_config import get_logger, setup_logger
from src.post_processor import process_responses_file
from src.prompt_generator import generate_prompts_from_file
from src.sequel2sql_client import Sequel2SQLClient
from src.ui import (
    ask_provider,
    ask_subset_size,
    confirm_delete,
    confirm_start,
    console,
    display_config_summary,
    display_error,
    display_logo,
    display_phase_header,
    display_results,
    display_success,
    get_previous_runs,
    show_main_menu,
    show_previous_runs_menu,
    show_run_details_and_confirm,
)


def check_docker():
    """
    Check if Docker is running.

    Returns:
        True if Docker is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "ps"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def start_docker_containers():
    """
    Start Docker containers for evaluation.

    Returns:
        True if successful, False otherwise
    """
    logger = get_logger()
    benchmark_dir = get_benchmark_dir()

    logger.info("Starting Docker containers...")

    try:
        # Check if containers are already running
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            cwd=benchmark_dir,
            timeout=10,
        )

        running_containers = result.stdout.strip().split("\n")

        if (
            "sequel2sql_postgresql" in running_containers
            and "sequel2sql_eval" in running_containers
        ):
            logger.info("✓ Docker containers already running")
            return True

        # Start containers
        logger.info("Building and starting containers (this may take a few minutes)...")
        result = subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            capture_output=True,
            text=True,
            cwd=benchmark_dir,
            timeout=600,  # 10 minutes for building
        )

        if result.returncode != 0:
            logger.error(f"Failed to start Docker containers: {result.stderr}")
            return False

        # Wait for PostgreSQL to be healthy
        logger.info("Waiting for PostgreSQL to be ready...")
        for i in range(30):
            result = subprocess.run(
                ["docker", "exec", "sequel2sql_postgresql", "pg_isready", "-U", "root"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.info("✓ PostgreSQL is ready")
                return True
            import time

            time.sleep(2)

        logger.error("PostgreSQL failed to become ready in time")
        return False

    except subprocess.TimeoutExpired:
        logger.error("Docker operation timed out")
        return False
    except Exception as e:
        logger.error(f"Error starting Docker containers: {e}")
        return False


def run_evaluation(final_output_path: Path, output_dir: Path, num_threads: int = 8):
    """
    Run PostgreSQL evaluation using wrapper script.

    Args:
        final_output_path: Path to final output JSONL with pred_sqls
        output_dir: Directory to save evaluation results
        num_threads: Number of evaluation threads

    Returns:
        True if successful, False otherwise
    """
    logger = get_logger()
    benchmark_dir = get_benchmark_dir()

    logger.info(f"Running evaluation with {num_threads} threads...")

    try:
        # Run evaluation inside Docker container
        cmd = [
            "docker",
            "exec",
            "sequel2sql_eval",
            "python",
            "src/wrapper_evaluation_postgresql.py",
            "--jsonl_file",
            str(final_output_path.relative_to(benchmark_dir)),
            "--num_threads",
            str(num_threads),
            "--mode",
            "pred",
            "--report",
            "true",
        ]

        result = subprocess.run(
            cmd,
            cwd=benchmark_dir,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hours max
        )

        if result.returncode != 0:
            logger.error(f"Evaluation failed: {result.stderr}")
            return False

        # Log output
        logger.info("Evaluation output:")
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                logger.info(f"  {line}")

        logger.info("✓ Evaluation complete")
        return True

    except subprocess.TimeoutExpired:
        logger.error("Evaluation timed out after 2 hours")
        return False
    except Exception as e:
        logger.error(f"Error running evaluation: {e}")
        return False


def main():
    """Main orchestrator function."""

    # ========== Parse Arguments ==========
    parser = argparse.ArgumentParser(
        description="SEQUEL2SQL Benchmark - Test SQL query debugging with LLMs"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of queries to process (useful for testing, e.g., --limit 20). If not provided, UI will prompt.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=DEFAULT_PROVIDER,
        choices=list(PROVIDERS.keys()),
        help=f"LLM provider to use. Choices: {', '.join(PROVIDERS.keys())}. Default: {DEFAULT_PROVIDER}",
    )
    args = parser.parse_args()
    # provider may be overridden interactively below when None
    cli_provider = args.provider if "--provider" in " ".join(sys.argv[1:]) else None
    provider = cli_provider or DEFAULT_PROVIDER

    # ========== Validate Configuration ==========
    # For CLI mode, validate immediately. For interactive mode, validate after provider is selected.
    if cli_provider is not None:
        try:
            validate_config(provider)
            model_config = get_model_config(provider)
        except SystemExit:
            return 1
        except Exception as e:
            display_error(f"Configuration error: {e}")
            return 1

    # ========== Display UI ==========
    display_logo()

    # Load dataset to get total count
    data_file = get_data_dir() / "postgresql_full.jsonl"
    import json
    import shutil

    with open(data_file, "r") as f:
        total_available_queries = sum(1 for _ in f)

    # ========== Main Menu Loop ==========
    query_limit = args.limit  # From command line
    output_dir = None
    checkpoint_manager = None
    resume_mode = False
    model_config = get_model_config(provider) if cli_provider is not None else None

    # If command line limit provided, skip menu and start directly
    if query_limit is not None:
        # If no explicit --provider given on CLI, ask interactively
        if model_config is None:
            selected_provider = ask_provider(PROVIDERS)
            if selected_provider is None:
                return 0
            try:
                validate_config(selected_provider)
                model_config = get_model_config(selected_provider)
            except SystemExit:
                return 1

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logger = setup_logger(timestamp)
        logger.info("=" * 70)
        logger.info("SEQUEL2SQL Benchmark Starting (command-line mode)")
        logger.info("=" * 70)

        total_queries = min(query_limit, total_available_queries)
        logger.info(f"⚠️  Running SUBSET MODE with {total_queries} queries")

        display_config_summary(model_config, total_queries)

        if not confirm_start():
            logger.info("User cancelled. Exiting...")
            return 0

        output_dir = get_outputs_dir() / f"run_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {output_dir}")

        checkpoint_manager = CheckpointManager(output_dir)
        checkpoint_manager.set_run_config(
            provider=provider if cli_provider is not None else selected_provider,
            model_id=model_config["model_id"],
            model_name=model_config["display_name"],
            pipeline_type="subset",
            query_limit=total_queries,
        )
        logger.info("Starting new run...")
    else:
        # Interactive menu
        while True:
            choice = show_main_menu()

            if not choice or choice.get("action") == "exit":
                return 0

            action = choice["action"]

            if action == "complete":
                # Ask which model to use
                selected_provider = ask_provider(PROVIDERS)
                if selected_provider is None:
                    continue
                try:
                    validate_config(selected_provider)
                    model_config = get_model_config(selected_provider)
                except SystemExit:
                    continue

                # Start complete run
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                logger = setup_logger(timestamp)
                logger.info("=" * 70)
                logger.info("SEQUEL2SQL Benchmark Starting - COMPLETE RUN")
                logger.info("=" * 70)

                query_limit = None
                total_queries = total_available_queries
                logger.info(f"Running FULL benchmark with {total_queries} queries")

                display_config_summary(model_config, total_queries)

                if not confirm_start():
                    continue

                output_dir = get_outputs_dir() / f"run_{timestamp}"
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Output directory: {output_dir}")

                checkpoint_manager = CheckpointManager(output_dir)
                checkpoint_manager.set_run_config(
                    provider=selected_provider,
                    model_id=model_config["model_id"],
                    model_name=model_config["display_name"],
                    pipeline_type="full",
                    query_limit=None,
                )
                resume_mode = False
                logger.info("Starting new complete run...")
                break

            elif action == "subset":
                # Ask which model to use
                selected_provider = ask_provider(PROVIDERS)
                if selected_provider is None:
                    continue
                try:
                    validate_config(selected_provider)
                    model_config = get_model_config(selected_provider)
                except SystemExit:
                    continue

                # Start subset run
                query_limit = ask_subset_size()
                if query_limit is None:
                    continue

                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                logger = setup_logger(timestamp)
                logger.info("=" * 70)
                logger.info("SEQUEL2SQL Benchmark Starting - SUBSET RUN")
                logger.info("=" * 70)

                total_queries = min(query_limit, total_available_queries)
                logger.info(f"⚠️  Running SUBSET MODE with {total_queries} queries")

                display_config_summary(model_config, total_queries)

                if not confirm_start():
                    continue

                output_dir = get_outputs_dir() / f"run_{timestamp}"
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Output directory: {output_dir}")

                checkpoint_manager = CheckpointManager(output_dir)
                checkpoint_manager.set_run_config(
                    provider=selected_provider,
                    model_id=model_config["model_id"],
                    model_name=model_config["display_name"],
                    pipeline_type="subset",
                    query_limit=total_queries,
                )
                resume_mode = False
                logger.info("Starting new subset run...")
                break

            elif action == "previous":
                # View previous runs
                runs = get_previous_runs(get_outputs_dir())
                selected_run = show_previous_runs_menu(runs)

                if selected_run is None:
                    continue

                # Show run details and ask what to do
                while True:
                    run_action = show_run_details_and_confirm(selected_run)

                    if run_action == "resume":
                        # Ask which model to use for this resumed run
                        selected_provider = ask_provider(PROVIDERS)
                        if selected_provider is None:
                            break
                        try:
                            validate_config(selected_provider)
                            model_config = get_model_config(selected_provider)
                        except SystemExit:
                            break

                        # Resume this run
                        timestamp = selected_run["timestamp"]
                        logger = setup_logger(f"{timestamp}_resumed")
                        logger.info("=" * 70)
                        logger.info("SEQUEL2SQL Benchmark - RESUMING RUN")
                        logger.info("=" * 70)

                        output_dir = selected_run["dir"]
                        checkpoint_manager = CheckpointManager(output_dir)
                        checkpoint_data = selected_run["checkpoint"]

                        query_limit = checkpoint_data.get("total_queries")
                        total_queries = query_limit

                        logger.info(f"Resuming run from {timestamp}")
                        logger.info(
                            f"Progress: {selected_run['completed']}/{total_queries} queries"
                        )

                        display_config_summary(model_config, total_queries)

                        resume_mode = True
                        logger.info("Resuming from checkpoint...")
                        break

                    elif run_action == "delete":
                        # Delete this run
                        if confirm_delete(selected_run):
                            try:
                                shutil.rmtree(selected_run["dir"])
                                console.print(
                                    f"\n[green]✓ Run deleted successfully.[/green]\n"
                                )
                                input("Press Enter to continue...")
                            except Exception as e:
                                console.print(
                                    f"\n[red]✗ Error deleting run: {e}[/red]\n"
                                )
                                input("Press Enter to continue...")
                        break

                    else:  # back
                        break

                if resume_mode:
                    break

    # ========== Phase 1: Prompt Generation ==========
    prompts_file = output_dir / "prompts.jsonl"

    if not prompts_file.exists():
        display_phase_header(
            "Phase 1: Prompt Generation",
            "Creating prompts with database schemas and problematic SQL...",
        )

        checkpoint_manager.set_phase("prompt_generation")

        try:
            num_generated = generate_prompts_from_file(
                data_file,
                prompts_file,
                schema_field="preprocess_schema",
                limit=query_limit,
            )
            logger.info(f"✓ Generated {num_generated} prompts")
            checkpoint_manager.save_checkpoint()
        except Exception as e:
            display_error(f"Prompt generation failed: {e}")
            logger.error(f"Prompt generation failed: {e}", exc_info=True)
            return 1
    else:
        logger.info("✓ Prompts already generated, skipping Phase 1")

    # ========== Phase 2: LLM Inference ==========
    responses_file = output_dir / "responses.jsonl"

    display_phase_header(
        "Phase 2: LLM Inference",
        f"Calling {model_config['display_name']} via pydantic-ai...",
    )

    checkpoint_manager.set_phase("inference")

    try:
        # Initialize LLM client
        # Sequel2SQL uses its own agentic pipeline — no external API client needed
        if model_config.get("no_api_key"):
            api_client = Sequel2SQLClient(model_config)
        else:
            api_client = LLMClient(model_config)

        # Initialize inference engine (sequential processing)
        inference_engine = InferenceEngine(
            api_client,
            checkpoint_manager,
            checkpoint_frequency=model_config["checkpoint_frequency"],
        )

        # Run inference
        num_processed = inference_engine.run_inference(
            prompts_file, responses_file, resume=resume_mode
        )

        logger.info(f"✓ Processed {num_processed} queries")

        # Display API statistics
        stats = api_client.get_statistics()
        logger.info(f"API Statistics:")
        logger.info(f"  Total requests: {stats['total_requests']}")
        logger.info(
            f"  Successful: {stats['successful_requests']} ({stats['success_rate']:.1f}%)"
        )
        logger.info(f"  Failed: {stats['failed_requests']}")

    except Exception as e:
        display_error(f"Inference failed: {e}")
        logger.error(f"Inference failed: {e}", exc_info=True)
        return 1

    # ========== Phase 3: Post-Processing ==========
    final_output_file = output_dir / "final_output.jsonl"

    if not final_output_file.exists():
        display_phase_header(
            "Phase 3: Post-Processing",
            "Extracting SQL statements from LLM responses...",
        )

        checkpoint_manager.set_phase("post_processing")

        try:
            num_processed = process_responses_file(responses_file, final_output_file)
            logger.info(f"✓ Processed {num_processed} responses")
            checkpoint_manager.save_checkpoint()
        except Exception as e:
            display_error(f"Post-processing failed: {e}")
            logger.error(f"Post-processing failed: {e}", exc_info=True)
            return 1
    else:
        logger.info("✓ SQL already extracted, skipping Phase 3")

    # ========== Phase 4: Docker Setup ==========
    display_phase_header(
        "Phase 4: Docker Setup", "Starting PostgreSQL and evaluation containers..."
    )

    # Check Docker
    if not check_docker():
        display_error(
            "Docker is not running. Please start Docker and try again.\n"
            "  On Linux: sudo systemctl start docker\n"
            "  On Mac/Windows: Start Docker Desktop"
        )
        return 1

    # Start containers
    if not start_docker_containers():
        display_error("Failed to start Docker containers. Check logs for details.")
        return 1

    logger.info("✓ Docker containers ready")

    # ========== Phase 5: Evaluation ==========
    # Skip if already completed
    if checkpoint_manager.is_evaluation_completed():
        logger.info("✓ Evaluation already completed, skipping Phase 5")
    else:
        display_phase_header(
            "Phase 5: Evaluation", "Running test cases against PostgreSQL database..."
        )

        checkpoint_manager.set_phase("evaluation")

        try:
            if not run_evaluation(
                final_output_file, output_dir, num_threads=model_config["max_threads"]
            ):
                display_error("Evaluation failed. Check logs for details.")
                logger.warning(
                    "You can resume this run later to retry evaluation only."
                )
                return 1

            # Mark evaluation as completed
            checkpoint_manager.set_evaluation_completed(True)
        except Exception as e:
            display_error(f"Evaluation error: {e}")
            logger.error(f"Evaluation error: {e}", exc_info=True)
            logger.warning("You can resume this run later to retry evaluation only.")
            return 1

    # ========== Display Results ==========
    logger.info("=" * 70)
    logger.info("Benchmark Complete!")
    logger.info("=" * 70)

    # Display summary statistics
    summary_stats = {
        "total_queries": checkpoint_manager.checkpoint_data["total_queries"],
        "completed_queries": checkpoint_manager.checkpoint_data["completed_queries"],
        "failed_queries": checkpoint_manager.checkpoint_data["failed_queries"],
        "total_api_calls": checkpoint_manager.checkpoint_data["statistics"][
            "total_api_calls"
        ],
        "average_query_time": checkpoint_manager.checkpoint_data["statistics"][
            "average_query_time"
        ],
    }

    display_results(summary_stats)

    # Show report file location
    report_file = final_output_file.parent / f"{final_output_file.stem}_report.txt"
    if report_file.exists():
        display_success(f"Evaluation report: {report_file}")

    logger.info(f"All outputs saved to: {output_dir}")
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user. Progress saved in checkpoint.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
