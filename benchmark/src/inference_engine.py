"""Inference engine for sequential LLM calls with progress tracking"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Set

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from .api_client import LLMClient
from .checkpoint_manager import CheckpointManager
from .logger_config import get_logger
from .prompt_generator import load_prompts


class InferenceEngine:
    """
    Sequential inference engine with checkpoint support.

    Features:
    - Sequential execution (one query at a time)
    - Progress bar with real-time statistics
    - Checkpoint saving every N queries
    - Resume from checkpoint capability
    """

    def __init__(
        self,
        api_client: LLMClient,
        checkpoint_manager: CheckpointManager,
        checkpoint_frequency: int = 10,
    ):
        """
        Initialize the inference engine.

        Args:
            api_client: Configured LLMClient instance
            checkpoint_manager: CheckpointManager instance
            checkpoint_frequency: Save checkpoint every N queries
        """
        self.api_client = api_client
        self.checkpoint_manager = checkpoint_manager
        self.checkpoint_frequency = checkpoint_frequency

        self.logger = get_logger()
        self.console = Console()

        # Statistics
        self.start_time = None
        self.queries_completed = 0

    def _worker(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Worker function to process a single query.

        Args:
            task_data: Dictionary with 'data' and 'index' keys

        Returns:
            Result dictionary with response
        """
        data = task_data["data"]
        index = task_data["index"]
        prompt = data["prompt"]

        try:
            # Call API
            response = self.api_client.call_api(prompt)

            # Create result
            result = {**data, "response": response, "_index": index}

            return {"success": True, "index": index, "result": result}

        except Exception as e:
            self.logger.error(
                f"Failed query {index} ({data.get('instance_id', 'unknown')}): {str(e)[:100]}"
            )
            return {"success": False, "index": index, "error": str(e)}

    def run_inference(
        self, prompts_path: Path, output_path: Path, resume: bool = False
    ) -> int:
        """
        Run inference on all prompts with multi-threading and progress tracking.

        Args:
            prompts_path: Path to prompts JSONL file
            output_path: Path to save responses
            resume: Whether to resume from checkpoint

        Returns:
            Number of queries processed
        """
        self.logger.info("Starting inference engine...")
        self.start_time = time.time()

        # Load prompts
        prompts_data = load_prompts(prompts_path)
        total_queries = len(prompts_data)

        # In resume mode, don't save checkpoint yet (it would overwrite completed_queries)
        self.checkpoint_manager.set_total_queries(total_queries, save=not resume)

        # Determine which queries to process
        if resume:
            completed_indices = self.checkpoint_manager.get_completed_indices()
            remaining_indices = [
                i for i in range(total_queries) if i not in completed_indices
            ]

            self.logger.info(
                f"Resuming: {len(completed_indices)} completed, {len(remaining_indices)} remaining"
            )
        else:
            remaining_indices = list(range(total_queries))
            self.logger.info(f"Starting fresh: {total_queries} queries to process")

        if not remaining_indices:
            self.logger.info("All queries already completed!")
            return 0

        # Prepare tasks
        tasks = [{"data": prompts_data[i], "index": i} for i in remaining_indices]

        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Run inference with progress bar
        self.logger.info(f"Processing {len(tasks)} queries sequentially...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(complete_style="green", finished_style="bold green"),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TextColumn("│"),
            TimeElapsedColumn(),
            TextColumn("│"),
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
        ) as progress:
            task_id = progress.add_task("Generating SQL Solutions", total=len(tasks))

            # Process tasks sequentially
            for task in tasks:
                index = task["index"]

                try:
                    result = self._worker(task)

                    if result["success"]:
                        # Write result immediately to file
                        with open(output_path, "a", encoding="utf-8") as f:
                            json.dump(result["result"], f, ensure_ascii=False)
                            f.write("\n")

                        self.queries_completed += 1

                        # Update checkpoint for each successful query
                        self.checkpoint_manager.update_progress(
                            index,
                            failed=False,
                            api_stats=self.api_client.get_statistics(),
                        )

                        # Save checkpoint every N queries
                        if self.queries_completed % self.checkpoint_frequency == 0:
                            self.checkpoint_manager.save()

                    else:
                        # Mark as failed
                        self.checkpoint_manager.update_progress(
                            index,
                            failed=True,
                            api_stats=self.api_client.get_statistics(),
                        )
                        self.checkpoint_manager.save()

                except Exception as e:
                    self.logger.error(f"Unexpected error processing query {index}: {e}")
                    self.checkpoint_manager.update_progress(
                        index,
                        failed=True,
                        api_stats=self.api_client.get_statistics(),
                    )
                    self.checkpoint_manager.save()

                # Update progress bar
                progress.update(task_id, advance=1)

                # Update description with current stats
                passed = self.queries_completed
                failed = self.checkpoint_manager.get_failed_count()
                model_name = self.api_client.model_config.get("display_name", "LLM")
                progress.update(
                    task_id,
                    description=f"Generating SQL Solutions [{model_name}] [green]\u2713{passed}[/green] [red]\u2717{failed}[/red]",
                )

        # Final checkpoint save
        self.checkpoint_manager.save()

        # Log statistics
        elapsed = time.time() - self.start_time
        queries_per_min = (self.queries_completed / elapsed) * 60 if elapsed > 0 else 0

        self.logger.info(f"✓ Inference complete!")
        self.logger.info(f"  Processed: {self.queries_completed} queries")
        self.logger.info(
            f"  Failed: {self.checkpoint_manager.get_failed_count()} queries"
        )
        self.logger.info(f"  Time: {elapsed:.1f}s ({queries_per_min:.1f} queries/min)")

        # Display API statistics
        stats = self.api_client.get_statistics()
        self.logger.info(
            f"  API calls: {stats['total_requests']} (success rate: {stats['success_rate']:.1f}%)"
        )

        return self.queries_completed


if __name__ == "__main__":
    # Test inference engine
    from datetime import datetime

    from .config import (
        DEFAULT_PROVIDER,
        get_data_dir,
        get_model_config,
        get_outputs_dir,
    )
    from .logger_config import setup_logger
    from .prompt_generator import generate_prompts_from_file

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger = setup_logger(timestamp)

    # Setup
    model_config = get_model_config(DEFAULT_PROVIDER)
    api_client = LLMClient(model_config)
    output_dir = get_outputs_dir() / f"test_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate test prompts (5 queries)
    data_file = get_data_dir() / "postgresql_full.jsonl"
    prompts_file = output_dir / "prompts.jsonl"

    logger.info("Generating test prompts...")
    generate_prompts_from_file(data_file, prompts_file, limit=5)

    # Initialize components
    checkpoint_manager = CheckpointManager(output_dir)

    # Run inference
    engine = InferenceEngine(api_client, checkpoint_manager, checkpoint_frequency=2)

    responses_file = output_dir / "responses.jsonl"
    num_processed = engine.run_inference(prompts_file, responses_file)

    print(f"\n✓ Inference test complete! Processed {num_processed} queries")
    print(f"  Output: {responses_file}\n")
