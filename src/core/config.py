import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

TEMP_DIR: Path = Path("temp")
BUILD_DIR: Path = Path("build")
CONFIG_PATH: Path = Path("config.toml")
SOURCES: tuple[str, ...] = ("archive", "apkmirror", "uptodown")
VALID_ARCHES: frozenset[str] = frozenset({"both", "all", "arm64-v8a", "arm-v7a", "x86_64", "x86"})


@dataclass(slots=True, frozen=True)
class Config:
    parallel_jobs: int
    patches_version: str
    cli_version: str
    patches_source: str
    cli_source: str
    brand: str

@dataclass(slots=True, frozen=True)
class AppEntry:
    table: str
    app_name: str
    brand: str
    arch: str
    dpi: str
    version: str
    uptodown_dlurl: str | None
    apkmirror_dlurl: str | None
    archive_dlurl: str | None
    patcher_args: str
    included_patches: str
    excluded_patches: str
    exclusive_patches: bool
    patches_source: str
    cli_source: str
    patches_version: str
    cli_version: str
    enabled: bool

    @property
    def dl_from(self) -> str | None:
        return next((src for src in SOURCES if getattr(self, f"{src}_dlurl") is not None), None)

def load_toml(path: Path) -> dict[str, object]:
    if path.suffix != ".toml":
        raise ValueError(f"Only .toml config files are supported, got: '{path}'")
    with path.open("rb") as fh:
        return tomllib.load(fh)

def parse_config(data: dict[str, object]) -> Config:
    return Config(
        parallel_jobs=int(data.get("parallel-jobs", os.cpu_count() or 1)),
        brand=str(data.get("brand", "Morphe")),
        patches_version=str(data.get("patches-version", "latest")),
        cli_version=str(data.get("cli-version", "latest")),
        patches_source=str(data.get("patches-source", "MorpheApp/morphe-patches")),
        cli_source=str(data.get("cli-source", "MorpheApp/morphe-cli")),
    )

def parse_app_entries(data: dict[str, object], main: Config) -> list[AppEntry]:
    entries: list[AppEntry] = []
    for table_name, t in data.items():
        if not isinstance(t, dict):
            continue

        if (arch := str(t.get("arch", "all"))) not in VALID_ARCHES:
            raise ValueError(f"Wrong arch '{arch}' for '{table_name}'")

        entries.append(AppEntry(
            table=table_name,
            app_name=str(t.get("app-name", table_name)),
            brand=str(t.get("brand", main.brand)),
            arch=arch,
            dpi=str(t.get("dpi", "")),
            version=str(t.get("version", "auto")),
            uptodown_dlurl=_clean_dlurl(t.get("uptodown-dlurl")),
            apkmirror_dlurl=_clean_dlurl(t.get("apkmirror-dlurl")),
            archive_dlurl=_clean_dlurl(t.get("archive-dlurl")),
            patcher_args=str(t.get("patcher-args", "")),
            included_patches=str(t.get("included-patches", "")),
            excluded_patches=str(t.get("excluded-patches", "")),
            exclusive_patches=_parse_bool(t.get("exclusive-patches", False), "exclusive-patches"),
            patches_source=str(t.get("patches-source", main.patches_source)),
            cli_source=str(t.get("cli-source", main.cli_source)),
            patches_version=str(t.get("patches-version", main.patches_version)),
            cli_version=str(t.get("cli-version", main.cli_version)),
            enabled=_parse_bool(t.get("enabled", True), "enabled"),
        ))
    return entries

def _clean_dlurl(url: object) -> str | None:
    return str(url).rstrip("/").removesuffix("download").rstrip("/") if isinstance(url, str) else None

def _parse_bool(value: object, field: str) -> bool:
    match value:
        case bool():
            return value
        case str() as v if v.lower() in ("true", "false"):
            return v.lower() == "true"
        case _:
            raise ValueError(f"'{value}' is not a valid option for '{field}': only true or false is allowed")
