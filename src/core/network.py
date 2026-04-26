import os
import threading
from pathlib import Path
from typing import Self
from curl_cffi import requests
from curl_cffi.requests import exceptions as req_exc

from src.core.logger import epr, pr


class NetworkError(Exception):
    pass

class NetworkManager:
    _download_locks: dict[Path, threading.Lock] = {}
    _locks_mutex: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self.session = requests.Session(impersonate="firefox147")
        token = os.getenv("GITHUB_TOKEN")
        self._gh_headers: dict[str, str] = {"Authorization": f"token {token}"} if token else {}

    def _fetch(self, url: str, headers: dict[str, str] | None = None, is_gh: bool = False) -> str:
        try:
            resp = self.session.get(url, timeout=10, allow_redirects=True, headers=headers)
            if (code := resp.status_code) >= 400:
                if is_gh:
                    epr(f"GitHub HTTP {code} for {url}: {resp.text[:200].replace('\n', ' ')}")
                else:
                    epr(f"HTTP {code} for {url}")
                resp.raise_for_status()
            return resp.text
        except req_exc.RequestException as exc:
            raise NetworkError(f"{'GitHub request' if is_gh else 'Request'} failed: {url}") from exc

    def get(self, url: str) -> str:
        return self._fetch(url)

    def download(self, url: str, dest: Path) -> None:
        self._stream_download(url, dest)

    def gh_get(self, url: str) -> str:
        return self._fetch(url, headers=self._gh_headers, is_gh=True)

    def gh_download(self, url: str, dest: Path) -> None:
        pr(f"Getting '{dest.name}' from '{url}'")
        self._stream_download(url, dest, headers=self._gh_headers | {"Accept": "application/octet-stream"}, is_gh=True)

    def _stream_download(self, url: str, dest: Path, headers: dict[str, str] | None = None, is_gh: bool = False) -> None:
        if dest.exists():
            return

        with self._get_lock(dest):
            if dest.exists():
                return

            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(f"tmp.{dest.name}")
            tmp.unlink(missing_ok=True)
            try:
                resp = self.session.get(url, timeout=10, stream=True, allow_redirects=True, headers=headers)
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(chunk_size=131072):
                        if chunk:
                            fh.write(chunk)
                tmp.replace(dest)
            except Exception as exc:
                tmp.unlink(missing_ok=True)
                raise NetworkError(f"{'GitHub download' if is_gh else 'Download'} failed: {url}") from exc
            finally:
                self._release_lock(dest)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.session.close()

    @classmethod
    def _get_lock(cls, key: Path) -> threading.Lock:
        with cls._locks_mutex:
            return cls._download_locks.setdefault(key, threading.Lock())

    @classmethod
    def _release_lock(cls, key: Path) -> None:
        with cls._locks_mutex:
            cls._download_locks.pop(key, None)
