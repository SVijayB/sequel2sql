"""Checkpoint manager for saving and resuming benchmark progress"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .logger_config import get_logger


class CheckpointManager:
    """
    Manages benchmark checkpoints for resume capability.

    Saves progress every N queries to allow resuming interrupted runs.
    """

    def __init__(self, output_dir: Path):
        """
        Initialize the checkpoint manager.

        Args:
            output_dir: Directory where checkpoint will be saved
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.output_dir / "checkpoint.json"
        self.logger = get_logger()

        # Try to load existing checkpoint, otherwise initialize with defaults
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    self.checkpoint_data = json.load(f)
                self.logger.info(
                    f"Loaded existing checkpoint: {self.checkpoint_data['completed_queries']}/{self.checkpoint_data['total_queries']} queries completed"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to load checkpoint, initializing new one: {e}"
                )
                self._initialize_checkpoint_data()
        else:
            self._initialize_checkpoint_data()

    def _initialize_checkpoint_data(self) -> None:
        """Initialize checkpoint data with default values."""
        self.checkpoint_data = {
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "phase": "initialization",
            "total_queries": 0,
            "completed_queries": 0,
            "failed_queries": 0,
            "current_api_key_index": 0,
            "completed_indices": [],
            "failed_indices": [],
            "evaluation_completed": False,
            "statistics": {
                "total_api_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_retries": 0,
                "key_usage": {},
                "average_query_time": 0.0,
                "inference_start_time": None,
                "inference_end_time": None,
                "estimated_completion_time": None,
            },
        }

    def checkpoint_exists(self) -> bool:
        """Check if a checkpoint file exists."""
        return self.checkpoint_file.exists()

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint from file.

        Returns:
            Checkpoint data dictionary or None if not found
        """
        if not self.checkpoint_exists():
            return None

        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.checkpoint_data = data
                self.logger.info(
                    f"Loaded checkpoint: {data['completed_queries']}/{data['total_queries']} queries completed"
                )
                return data
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint: {e}")
            return None

    def save_checkpoint(self, updates: Optional[Dict[str, Any]] = None) -> None:
        """
        Save checkpoint to file.

        Args:
            updates: Optional dictionary of fields to update before saving
        """
        if updates:
            self.checkpoint_data.update(updates)

        self.checkpoint_data["last_updated"] = datetime.now().isoformat()

        try:
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(self.checkpoint_data, f, indent=2, ensure_ascii=False)

            self.logger.debug(
                f"Checkpoint saved: {self.checkpoint_data['completed_queries']}/{self.checkpoint_data['total_queries']} queries"
            )
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")

    def update_progress(
        self,
        completed_index: int,
        failed: bool = False,
        api_stats: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update progress after completing a query.

        Args:
            completed_index: Index of the completed query
            failed: Whether the query failed
            api_stats: Optional API client statistics
        """
        if failed:
            if completed_index not in self.checkpoint_data["failed_indices"]:
                self.checkpoint_data["failed_indices"].append(completed_index)
                self.checkpoint_data["failed_queries"] += 1
        else:
            if completed_index not in self.checkpoint_data["completed_indices"]:
                self.checkpoint_data["completed_indices"].append(completed_index)
                self.checkpoint_data["completed_queries"] = len(
                    self.checkpoint_data["completed_indices"]
                )

        # Update API statistics if provided
        if api_stats:
            self.checkpoint_data["current_api_key_index"] = api_stats.get(
                "current_key_index", 0
            )
            self.checkpoint_data["statistics"]["total_api_calls"] = api_stats.get(
                "total_requests", 0
            )
            self.checkpoint_data["statistics"]["successful_calls"] = api_stats.get(
                "successful_requests", 0
            )
            self.checkpoint_data["statistics"]["failed_calls"] = api_stats.get(
                "failed_requests", 0
            )
            self.checkpoint_data["statistics"]["key_usage"] = api_stats.get(
                "key_usage", {}
            )

            # Calculate average query time
            if self.checkpoint_data["completed_queries"] > 0:
                start_time = self.checkpoint_data["statistics"].get(
                    "inference_start_time"
                )
                if start_time:
                    elapsed = (
                        datetime.now() - datetime.fromisoformat(start_time)
                    ).total_seconds()
                    self.checkpoint_data["statistics"]["average_query_time"] = (
                        elapsed / self.checkpoint_data["completed_queries"]
                    )

        # Save checkpoint
        self.save_checkpoint()

    def get_remaining_queries(self, total_queries: int) -> List[int]:
        """
        Get list of query indices that haven't been completed.

        Args:
            total_queries: Total number of queries in the dataset

        Returns:
            List of remaining query indices
        """
        completed = set(self.checkpoint_data["completed_indices"])
        return [i for i in range(total_queries) if i not in completed]

    def get_completed_indices(self) -> Set[int]:
        """Get set of completed query indices."""
        return set(self.checkpoint_data["completed_indices"])

    def get_failed_indices(self) -> Set[int]:
        """Get set of failed query indices."""
        return set(self.checkpoint_data["failed_indices"])

    def get_failed_count(self) -> int:
        """Get count of failed queries."""
        return self.checkpoint_data["failed_queries"]

    def set_phase(self, phase: str) -> None:
        """
        Set the current benchmark phase.

        Args:
            phase: Phase name (prompt_generation, inference, post_processing, evaluation)
        """
        self.checkpoint_data["phase"] = phase

        # Track inference start time
        if phase == "inference" and not self.checkpoint_data["statistics"].get(
            "inference_start_time"
        ):
            self.checkpoint_data["statistics"]["inference_start_time"] = (
                datetime.now().isoformat()
            )

        # Track inference end time
        if phase == "post_processing" and not self.checkpoint_data["statistics"].get(
            "inference_end_time"
        ):
            self.checkpoint_data["statistics"]["inference_end_time"] = (
                datetime.now().isoformat()
            )

        self.save_checkpoint()

    def set_evaluation_completed(self, completed: bool = True) -> None:
        """Mark evaluation as completed."""
        self.checkpoint_data["evaluation_completed"] = completed
        self.save_checkpoint()

    def is_evaluation_completed(self) -> bool:
        """Check if evaluation is completed."""
        return self.checkpoint_data.get("evaluation_completed", False)

    def set_total_queries(self, total: int, save: bool = True) -> None:
        """Set the total number of queries.

        Args:
            total: Total number of queries
            save: Whether to save checkpoint immediately (default True)
        """
        self.checkpoint_data["total_queries"] = total
        if save:
            self.save_checkpoint()

    def get_progress_percentage(self) -> float:
        """Get progress as percentage."""
        total = self.checkpoint_data["total_queries"]
        completed = self.checkpoint_data["completed_queries"]
        if total == 0:
            return 0.0
        return (completed / total) * 100

    def clear(self) -> None:
        """Clear checkpoint (for restart)."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            self.logger.info("Checkpoint cleared")

    def save(self) -> None:
        """Save the current checkpoint state."""
        self.save_checkpoint()

    def get_summary(self) -> Dict[str, Any]:
        """Get checkpoint summary for display."""
        return {
            "phase": self.checkpoint_data["phase"],
            "total_queries": self.checkpoint_data["total_queries"],
            "completed_queries": self.checkpoint_data["completed_queries"],
            "failed_queries": self.checkpoint_data["failed_queries"],
            "progress_percentage": self.get_progress_percentage(),
            "created_at": self.checkpoint_data["created_at"],
            "last_updated": self.checkpoint_data["last_updated"],
            "current_api_key": self.checkpoint_data["current_api_key_index"] + 1,
            "statistics": self.checkpoint_data["statistics"],
        }


if __name__ == "__main__":
    # Test checkpoint manager
    from datetime import datetime

    from .logger_config import setup_logger

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    setup_logger(timestamp)

    # Create test checkpoint
    output_dir = Path("test_output")
    manager = CheckpointManager(output_dir)

    # Simulate progress
    manager.set_total_queries(531)
    manager.set_phase("inference")

    for i in range(10):
        manager.update_progress(i, failed=(i % 7 == 0))

    # Test load
    summary = manager.get_summary()
    print("\nCheckpoint Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    # Test remaining queries
    remaining = manager.get_remaining_queries(20)
    print(f"\nRemaining queries (out of 20): {remaining}")

    # Cleanup
    manager.clear()
    output_dir.rmdir()

    print("\n✓ Checkpoint manager test complete!")
