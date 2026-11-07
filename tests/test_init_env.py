import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "init_env", Path(__file__).resolve().parents[1] / "scripts" / "init_env.py"
)
assert SPEC and SPEC.loader
init_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(init_env)


def test_creates_env_and_generates_empty_secrets(tmp_path: Path) -> None:
    example = tmp_path / "example"
    example.write_text("# c\nA=1\nX_PASSWORD=\nY_SECRET=\nZ_API_KEY=\nW_PASSWORD=fixed\n")
    env = tmp_path / ".env"
    init_env.sync(example, env)
    values = init_env.parse_keys(env.read_text())
    assert values["A"] == "1"
    assert len(values["X_PASSWORD"]) == 48
    assert len(values["Y_SECRET"]) == 48
    assert values["Z_API_KEY"] == ""
    assert values["W_PASSWORD"] == "fixed"
    assert env.read_text().startswith("# c\n")


def test_appends_only_missing_keys_and_keeps_existing_values(tmp_path: Path) -> None:
    example = tmp_path / "example"
    example.write_text("A=1\nB_SECRET=\n")
    env = tmp_path / ".env"
    env.write_text("A=custom\n")
    assert init_env.sync(example, env) == ["B_SECRET"]
    values = init_env.parse_keys(env.read_text())
    assert values["A"] == "custom"
    assert values["B_SECRET"]
    assert init_env.sync(example, env) == []
