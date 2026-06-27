"""Skill manager — loads and matches Claude Code-style skill definitions.

Skills are YAML files or Claude Code SKILL.md files that define trigger
keywords and prompt instructions. When a user message matches a skill's triggers,
that skill's prompt is injected into the system prompt, giving the LLM specialized
knowledge for that task.
"""

import re
import shutil
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class Skill:
    """Represents a loaded skill definition."""
    name: str
    description: str = ""
    triggers: list[str] = field(default_factory=list)
    prompt: str = ""
    file_path: str = ""

    def matches(self, message: str) -> bool:
        """Check if this skill's triggers match the given message."""
        message_lower = message.lower()
        for trigger in self.triggers:
            # Support simple keyword matching and regex patterns
            # If trigger contains regex-like syntax, use regex matching
            if any(c in trigger for c in [".*", ".+", "[", "(", "\\", "^", "$"]):
                try:
                    if re.search(trigger, message_lower):
                        return True
                except re.error:
                    pass

            # Simple substring match
            if trigger.lower() in message_lower:
                return True

        return False

    def __repr__(self) -> str:
        return f"Skill(name='{self.name}', triggers={self.triggers[:3]})"


class SkillManager:
    """Loads and manages skill definitions."""

    def __init__(self, skills_dir: str = "skills"):
        self._skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all skill files from the skills directory."""
        if not self._skills_dir.exists():
            logger.warning("Skills directory not found: %s", self._skills_dir)
            return

        # Load YAML files
        for yaml_file in sorted(self._skills_dir.glob("*.yaml")):
            skill = self._load_single_file(yaml_file)
            if skill:
                self._skills[skill.name] = skill

        # Load Claude Code SKILL.md files (in subdirectories too)
        for skill_md in sorted(self._skills_dir.rglob("SKILL.md")):
            skill = self._load_skill_md(skill_md)
            if skill:
                self._skills[skill.name] = skill

    def _load_single_file(self, yaml_path: Path) -> Skill | None:
        """Load a single YAML skill file and return the Skill object."""
        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data or "name" not in data:
                logger.warning("Skipping invalid skill file: %s", yaml_path)
                return None

            skill = Skill(
                name=data.get("name", yaml_path.stem),
                description=data.get("description", ""),
                triggers=data.get("triggers", []),
                prompt=data.get("prompt", ""),
                file_path=str(yaml_path),
            )
            logger.info("Loaded skill: %s (triggers: %d)", skill.name, len(skill.triggers))
            return skill
        except Exception as e:
            logger.error("Failed to load skill %s: %s", yaml_path, e)
            return None

    def _load_skill_md(self, md_path: Path) -> Skill | None:
        """Load a Claude Code SKILL.md file.

        Format:
        ---
        name: skill-name
        description: |
          Description with trigger words
        ---
        Markdown content...
        """
        try:
            with open(md_path, encoding="utf-8") as f:
                content = f.read()

            # Parse frontmatter (--- ... ---)
            frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if not frontmatter_match:
                logger.warning("No frontmatter found in SKILL.md: %s", md_path)
                return None

            frontmatter_yaml = frontmatter_match.group(1)
            data = yaml.safe_load(frontmatter_yaml)

            if not data or "name" not in data:
                logger.warning("Invalid frontmatter in SKILL.md: %s", md_path)
                return None

            # Extract the rest of the content as prompt
            prompt = content[frontmatter_match.end():].strip()
            description = data.get("description", "")

            # Extract trigger words from description
            triggers = self._extract_triggers_from_description(description)

            # Also use the skill name as a trigger
            skill_name = data.get("name", md_path.parent.name)
            if skill_name and skill_name not in triggers:
                triggers.append(skill_name)

            skill = Skill(
                name=skill_name,
                description=description,
                triggers=triggers,
                prompt=prompt,
                file_path=str(md_path),
            )
            logger.info("Loaded Claude Code skill: %s (triggers: %d)", skill.name, len(skill.triggers))
            return skill
        except Exception as e:
            logger.error("Failed to load SKILL.md %s: %s", md_path, e)
            return None

    def _extract_triggers_from_description(self, description: str) -> list[str]:
        """Extract trigger words from Claude Code skill description.

        Looks for patterns like:
        - 「雪乃」「雪之下」
        - 触发词：X, Y, Z
        - 触发词: X, Y, Z
        - 「...」 or "..." quoted terms
        """
        triggers = []

        # Look for 「...」 and "..." quoted strings
        quoted_matches = re.findall(r'[「"](.*?)[」"]', description)
        for match in quoted_matches:
            if match and len(match) > 1:
                triggers.append(match)

        # Look for "触发词：" or "trigger words:" patterns
        trigger_line_match = re.search(
            r'(?:触发词|触发|trigger)[：:]\s*(.+?)(?:\n|$)',
            description,
            re.IGNORECASE
        )
        if trigger_line_match:
            trigger_line = trigger_line_match.group(1)
            # Split by common separators
            terms = re.split(r'[、，,、\s]+', trigger_line)
            for term in terms:
                term = term.strip()
                if term and term not in triggers:
                    triggers.append(term)

        # Also look for "即使用户只是说..." pattern
        also_trigger_match = re.search(
            r'即使.*?(?:说|问)\s*[「"](.+?)[」"]',
            description
        )
        if also_trigger_match:
            term = also_trigger_match.group(1).strip()
            if term and term not in triggers:
                triggers.append(term)

        return triggers

    def add_skill_from_path(self, source_path: str, copy: bool = True) -> Skill | None:
        """Add a skill from an external file or directory.

        Args:
            source_path: Path to the YAML skill file, SKILL.md file, or directory
            copy: If True, copy the file/directory to the skills directory;
                  if False, load directly from source_path

        Returns:
            The loaded Skill object, or None if loading failed
        """
        src = Path(source_path)
        if not src.exists():
            logger.error("Skill file not found: %s", source_path)
            return None

        # Ensure skills directory exists
        if not self._skills_dir.exists():
            self._skills_dir.mkdir(parents=True, exist_ok=True)

        target_path = src
        skill = None

        # Handle directory (look for SKILL.md inside)
        if src.is_dir():
            skill_md = src / "SKILL.md"
            if skill_md.exists():
                if copy:
                    dest_dir = self._skills_dir / src.name
                    counter = 1
                    while dest_dir.exists():
                        dest_dir = self._skills_dir / f"{src.name}_{counter}"
                        counter += 1
                    shutil.copytree(src, dest_dir)
                    logger.info("Copied skill directory to: %s", dest_dir)
                    target_path = dest_dir / "SKILL.md"
                else:
                    target_path = skill_md
                skill = self._load_skill_md(target_path)
        # Handle SKILL.md file
        elif src.name == "SKILL.md":
            if copy:
                # Create a directory for this skill
                dest_dir = self._skills_dir / src.parent.name or "skill"
                counter = 1
                while dest_dir.exists():
                    dest_dir = self._skills_dir / f"{(src.parent.name or 'skill')}_{counter}"
                    counter += 1
                dest_dir.mkdir(parents=True)
                dest = dest_dir / "SKILL.md"
                shutil.copy2(src, dest)
                # Also copy references directory if exists
                ref_dir = src.parent / "references"
                if ref_dir.exists():
                    shutil.copytree(ref_dir, dest_dir / "references")
                logger.info("Copied SKILL.md to: %s", dest)
                target_path = dest
            skill = self._load_skill_md(target_path)
        # Handle YAML file
        elif src.suffix in (".yaml", ".yml"):
            if copy:
                dest = self._skills_dir / src.name
                counter = 1
                while dest.exists():
                    dest = self._skills_dir / f"{src.stem}_{counter}{src.suffix}"
                    counter += 1
                shutil.copy2(src, dest)
                logger.info("Copied skill file to: %s", dest)
                target_path = dest
            skill = self._load_single_file(target_path)
        # Unknown format
        else:
            logger.error("Unsupported skill format: %s", source_path)
            return None

        if skill:
            self._skills[skill.name] = skill

        return skill

    def remove_skill(self, skill_name: str, delete_file: bool = False) -> bool:
        """Remove a skill by name.

        Args:
            skill_name: Name of the skill to remove
            delete_file: If True, also delete the file from disk

        Returns:
            True if the skill was found and removed
        """
        skill = self._skills.get(skill_name)
        if not skill:
            logger.warning("Skill not found for removal: %s", skill_name)
            return False

        if delete_file and skill.file_path:
            try:
                Path(skill.file_path).unlink(missing_ok=True)
                logger.info("Deleted skill file: %s", skill.file_path)
            except Exception as e:
                logger.error("Failed to delete skill file: %s", e)

        del self._skills[skill_name]
        logger.info("Removed skill: %s", skill_name)
        return True

    def reload(self) -> None:
        """Reload all skills from the skills directory."""
        logger.info("Reloading all skills...")
        self._skills.clear()
        self._load_all()

    def match(self, message: str) -> list[Skill]:
        """Find all skills whose triggers match the given message."""
        matched = []
        for skill in self._skills.values():
            if skill.matches(message):
                matched.append(skill)
                logger.debug("Skill matched: %s for message: %.50s...", skill.name, message)
        return matched

    def build_skill_prompt(self, message: str, max_skills: int = 3) -> str:
        """
        Build a prompt fragment from matched skills for the given message.

        Args:
            message: The user's message text.
            max_skills: Maximum number of matched skills to include.

        Returns:
            A string to append to the system prompt, or empty string if no matches.
        """
        matched = self.match(message)
        if not matched:
            return ""

        # Limit to max_skills to avoid overflowing the system prompt
        matched = matched[:max_skills]

        parts = ["\n\n## 以下是你需要运用的专业技能知识:\n"]
        for skill in matched:
            parts.append(f"### {skill.name}")
            parts.append(skill.prompt.strip())
            parts.append("")

        return "\n".join(parts)

    def list_skills(self) -> list[Skill]:
        """Return all loaded skills."""
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)
