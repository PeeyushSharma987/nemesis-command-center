import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MistakeEntry(BaseModel):
    task_type: str
    what_went_wrong: str
    permanent_fix_rule: str
    timestamp: float = Field(default_factory=time.time)


class UserDigitalTwin(BaseModel):
    user_id: str
    savage_level: int = Field(default=80, ge=10, le=100)
    favorite_song: Optional[str] = None
    registered_devices: List[str] = Field(default_factory=list)
    preferred_stack: Dict[str, str] = Field(default_factory=dict)
    custom_facts: Dict[str, Any] = Field(default_factory=dict)


class MemoryAndMistakeVault:
    """Manages per-user Digital Twin profiles and the Anti-Pattern Mistake Ledger."""

    def __init__(self, storage_dir: Path = Path("nemesis_memory_store")) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.mistakes_file = self.storage_dir / "episodic_mistake_ledger.json"
        if not self.mistakes_file.exists():
            self.mistakes_file.write_text("[]", encoding="utf-8")

    def _twin_path(self, user_id: str) -> Path:
        safe_id = "".join(c for c in user_id if c.isalnum() or c in ("-", "_"))
        return self.storage_dir / f"twin_{safe_id}.json"

    def get_user_twin(self, user_id: str) -> UserDigitalTwin:
        path = self._twin_path(user_id)
        if path.exists():
            return UserDigitalTwin(**json.loads(path.read_text(encoding="utf-8")))
        twin = UserDigitalTwin(user_id=user_id)
        self.save_user_twin(twin)
        return twin

    def save_user_twin(self, twin: UserDigitalTwin) -> None:
        self._twin_path(twin.user_id).write_text(
            json.dumps(twin.model_dump(), indent=2),
            encoding="utf-8",
        )

    def update_user_fact(self, user_id: str, key: str, value: Any) -> UserDigitalTwin:
        twin = self.get_user_twin(user_id)
        if key == "favorite_song":
            twin.favorite_song = str(value)
        elif key == "savage_level":
            twin.savage_level = max(10, min(100, int(value)))
        else:
            twin.custom_facts[key] = value
        self.save_user_twin(twin)
        return twin

    def record_mistake(self, entry: MistakeEntry) -> Dict[str, Any]:
        ledger: List[Dict[str, Any]] = json.loads(self.mistakes_file.read_text(encoding="utf-8"))
        ledger.append(entry.model_dump())
        self.mistakes_file.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        return {"status": "logged", "total_rules_learned": len(ledger)}

    def get_anti_pattern_rules(self, task_type: Optional[str] = None) -> List[str]:
        ledger: List[Dict[str, Any]] = json.loads(self.mistakes_file.read_text(encoding="utf-8"))
        rules = [
            f"[AVOID PAST MISTAKE in {item['task_type']}]: {item['permanent_fix_rule']}"
            for item in ledger
            if not task_type or item["task_type"].lower() == task_type.lower()
        ]
        return rules[-10:]
