"""Character manager — loads and manages AI character profiles."""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class Character:
    """Represents a loaded character profile."""
    name: str
    description: str = ""
    personality: str = ""
    background: str = ""
    speaking_style: str = ""
    system_prompt: str = ""
    file_path: str = ""
    # List of skill names that are bound to this character (auto-loaded)
    bound_skills: list[str] = field(default_factory=list)

    def build_system_prompt(self) -> str:
        """Build the full system prompt from character attributes."""
        parts = []

        if self.system_prompt:
            parts.append(self.system_prompt)
        else:
            # Fallback: build from individual attributes
            parts.append(f"你是{self.name}。")
            if self.background:
                parts.append(f"背景: {self.background}")
            if self.personality:
                parts.append(f"性格: {self.personality}")
            if self.speaking_style:
                parts.append(f"说话风格: {self.speaking_style}")
            parts.append("")
            parts.append("请遵循以下规则:")
            parts.append("1. 用友好、自然的语气回复，回复尽量简洁")
            parts.append("2. 如果不知道答案，诚实地说不知道")
            parts.append("3. 使用中文回复")
            parts.append("4. 不要提及你是 AI 或模型，表现得像一个热心的群友")

        return "\n".join(parts)

    def to_dict(self) -> dict:
        """Convert character to dict for saving to YAML."""
        return {
            "name": self.name,
            "description": self.description,
            "personality": self.personality,
            "background": self.background,
            "speaking_style": self.speaking_style,
            "system_prompt": self.system_prompt,
            "bound_skills": self.bound_skills,
        }

    def __repr__(self) -> str:
        return f"Character(name='{self.name}', description='{self.description}')"


class CharacterManager:
    """Loads, caches, and switches between character profiles."""

    def __init__(self, characters_dir: str = "characters", default_character: str = "default"):
        self._characters_dir = Path(characters_dir)
        self._characters: dict[str, Character] = {}
        self._active_name: str | None = None
        self._default_name = default_character

        self._load_all()

        # Set active character
        if default_character in self._characters:
            self._active_name = default_character
        elif self._characters:
            self._active_name = next(iter(self._characters))
            logger.warning(
                "Default character '%s' not found, using '%s'",
                default_character, self._active_name,
            )
        else:
            logger.error("No character files found in %s", self._characters_dir)

    def _load_all(self) -> None:
        """Load all character YAML files from the characters directory."""
        if not self._characters_dir.exists():
            logger.warning("Characters directory not found: %s", self._characters_dir)
            return

        for yaml_file in sorted(self._characters_dir.glob("*.yaml")):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not data or "name" not in data:
                    logger.warning("Skipping invalid character file: %s", yaml_file)
                    continue

                char = Character(
                    name=data.get("name", yaml_file.stem),
                    description=data.get("description", ""),
                    personality=data.get("personality", ""),
                    background=data.get("background", ""),
                    speaking_style=data.get("speaking_style", ""),
                    system_prompt=data.get("system_prompt", ""),
                    bound_skills=data.get("bound_skills", []),
                    file_path=str(yaml_file),
                )
                key = yaml_file.stem  # filename without extension
                self._characters[key] = char
                logger.info("Loaded character: %s (%s) with %d bound skills",
                            char.name, key, len(char.bound_skills))
            except Exception as e:
                logger.error("Failed to load character %s: %s", yaml_file, e)

    def _load_single_file(self, yaml_path: Path) -> Character | None:
        """Load a single character file."""
        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data or "name" not in data:
                logger.warning("Invalid character file: %s", yaml_path)
                return None

            return Character(
                name=data.get("name", yaml_path.stem),
                description=data.get("description", ""),
                personality=data.get("personality", ""),
                background=data.get("background", ""),
                speaking_style=data.get("speaking_style", ""),
                system_prompt=data.get("system_prompt", ""),
                bound_skills=data.get("bound_skills", []),
                file_path=str(yaml_path),
            )
        except Exception as e:
            logger.error("Failed to load character %s: %s", yaml_path, e)
            return None

    def save_character(self, character: Character, key: str | None = None) -> bool:
        """Save a character to its YAML file. If key is given, uses that as filename."""
        try:
            if not self._characters_dir.exists():
                self._characters_dir.mkdir(parents=True, exist_ok=True)

            if key is None:
                # Use existing key from file_path or derive from name
                if character.file_path:
                    key = Path(character.file_path).stem
                else:
                    key = character.name.replace(" ", "_").lower()

            yaml_path = self._characters_dir / f"{key}.yaml"

            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(character.to_dict(), f, allow_unicode=True,
                          default_flow_style=False, sort_keys=False)

            character.file_path = str(yaml_path)
            self._characters[key] = character

            logger.info("Saved character: %s to %s", character.name, yaml_path)
            return True
        except Exception as e:
            logger.error("Failed to save character %s: %s", character.name, e)
            return False

    def delete_character(self, key: str, delete_file: bool = False) -> bool:
        """Delete a character. Returns True if successful."""
        if key not in self._characters:
            return False

        char = self._characters[key]

        if delete_file and char.file_path:
            try:
                Path(char.file_path).unlink(missing_ok=True)
                logger.info("Deleted character file: %s", char.file_path)
            except Exception as e:
                logger.error("Failed to delete character file: %s", e)

        del self._characters[key]

        # If active character was deleted, switch to another
        if self._active_name == key:
            if self._characters:
                self._active_name = next(iter(self._characters))
            else:
                self._active_name = None

        logger.info("Deleted character: %s", char.name)
        return True

    def reload(self) -> None:
        """Reload all characters from disk."""
        logger.info("Reloading all characters...")
        self._characters.clear()
        self._load_all()

    @property
    def active(self) -> Character | None:
        """Get the currently active character."""
        if self._active_name:
            return self._characters.get(self._active_name)
        return None

    def switch(self, name_or_key: str) -> Character | None:
        """Switch to a character by name or key. Returns the new character or None."""
        # First try exact key match
        if name_or_key in self._characters:
            self._active_name = name_or_key
            logger.info("Switched to character: %s", self._characters[name_or_key].name)
            return self._characters[name_or_key]

        # Then try matching by display name
        for key, char in self._characters.items():
            if char.name == name_or_key:
                self._active_name = key
                logger.info("Switched to character: %s", char.name)
                return char

        logger.warning("Character not found: %s", name_or_key)
        return None

    def list_characters(self) -> list[Character]:
        """Return all loaded characters."""
        return list(self._characters.values())

    def get(self, key: str) -> Character | None:
        """Get a character by key."""
        return self._characters.get(key)

    def get_by_name(self, name: str) -> Character | None:
        """Get a character by display name (case-insensitive)."""
        name_lower = name.lower()
        for char in self._characters.values():
            if char.name.lower() == name_lower:
                return char
        return None
