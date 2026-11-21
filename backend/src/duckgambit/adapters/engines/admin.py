"""EngineAdmin over the manifest catalog and the installer."""

from __future__ import annotations

from duckgambit.adapters.engines.catalog import EngineCatalog
from duckgambit.adapters.engines.installer import EngineInstaller, InstallError
from duckgambit.services.engines import EngineListing
from duckgambit.services.ports import EngineError


class CatalogEngineAdmin:
    def __init__(self, catalog: EngineCatalog, installer: EngineInstaller) -> None:
        self._catalog = catalog
        self._installer = installer

    def known(self, engine_id: str) -> bool:
        return self._catalog.entry(engine_id) is not None

    def listings(self) -> list[EngineListing]:
        result = []
        for entry in self._catalog.entries():
            installed = self._catalog.installed(entry.id)
            if self._installer.is_busy(entry.id):
                status = "installing"
            elif installed is not None:
                status = "installed"
            elif self._catalog.asset(entry.id) is None:
                status = "unavailable"
            else:
                status = "not_installed"
            result.append(
                EngineListing(
                    id=entry.id,
                    name=entry.name,
                    version=entry.version,
                    license=entry.license,
                    homepage=entry.homepage,
                    source_url=entry.source_url,
                    status=status,
                    fingerprint=installed.binary_sha256[:16] if installed else None,
                )
            )
        return result

    async def install(self, engine_id: str) -> None:
        try:
            await self._installer.install(engine_id)
        except InstallError as exc:
            raise EngineError(exc.code, exc.message) from exc
        except OSError as exc:
            raise EngineError(
                "engine.install_failed", "The engine files could not be written (is it in use?)"
            ) from exc

    async def remove(self, engine_id: str) -> None:
        try:
            await self._installer.remove(engine_id)
        except InstallError as exc:
            raise EngineError(exc.code, exc.message) from exc
