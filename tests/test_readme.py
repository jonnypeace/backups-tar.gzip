import re
from pathlib import Path

import yaml

from backups_tar_gzip.backup import Config

README_PATH = Path(__file__).parent.parent / "README.md"
SAMPLE_CONFIG_PATH = (
    Path(__file__).parent.parent / "test_yaml_config" / "sample_config.yaml"
)


def yaml_blocks(text: str) -> list[str]:
    return re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)


def test_readme_config_example_is_valid() -> None:
    """The README's full config example must validate against the pydantic
    models, so docs can't drift when config options change."""
    blocks: list[str] = yaml_blocks(README_PATH.read_text())
    full_example: str | None = next(
        (b for b in blocks if "defaults:" in b and "projects:" in b), None
    )
    assert full_example is not None, "README no longer contains a full config example"
    Config.model_validate(yaml.safe_load(full_example))


def test_sample_config_is_valid() -> None:
    """test_yaml_config/sample_config.yaml must validate too, for the same
    reason as the README example."""
    assert SAMPLE_CONFIG_PATH.exists(), f"sample config not found: {SAMPLE_CONFIG_PATH}"
    Config.model_validate(yaml.safe_load(SAMPLE_CONFIG_PATH.read_text()))