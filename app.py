from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

LOGGER = logging.getLogger(__name__)
SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)


class ConfigurationError(RuntimeError):
    """Indica uma variável de ambiente obrigatória ausente ou inválida."""


class GoogleSheetsError(RuntimeError):
    """Indica uma falha segura de expor da integração com o Google Sheets."""


@dataclass(frozen=True)
class Settings:
    spreadsheet_id: str
    worksheet: str
    range_name: str
    token_file: Path


class Column(BaseModel):
    key: str
    label: str


class InventoryReport(BaseModel):
    columns: list[Column]
    items: list[dict[str, str]]
    values: dict[str, dict[str, str]]
    total: int


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Variável obrigatória ausente: {name}.")
    return value


def get_settings() -> Settings:
    return Settings(
        spreadsheet_id=_required_env("INVENTARIO_SPREADSHEET_ID"),
        worksheet=_required_env("INVENTARIO_WORKSHEET"),
        range_name=os.getenv("INVENTARIO_RANGE", "A:AA").strip() or "A:AA",
        token_file=Path(_required_env("GOOGLE_SHEETS_TOKEN_FILE")),
    )


def _json_key(label: str, index: int, used_keys: set[str]) -> str:
    normalized = unicodedata.normalize("NFKD", label)
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    base = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")
    base = base or f"coluna_{index + 1}"

    key = base
    suffix = 2
    while key in used_keys:
        key = f"{base}_{suffix}"
        suffix += 1

    used_keys.add(key)
    return key


def _get_google_service(settings: Settings) -> Any:
    if not settings.token_file.is_file():
        raise ConfigurationError(
            "Token Google não encontrado no caminho configurado em "
            "GOOGLE_SHEETS_TOKEN_FILE."
        )

    try:
        credentials = Credentials.from_authorized_user_file(
            str(settings.token_file),
            SCOPES,
        )
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            settings.token_file.write_text(credentials.to_json(), encoding="utf-8")
    except (OSError, RefreshError, ValueError) as error:
        raise GoogleSheetsError("Não foi possível validar ou renovar o token Google.") from error

    if not credentials.valid:
        raise GoogleSheetsError("Token Google inválido ou expirado sem refresh token.")

    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def consultar_respostas_inventario(
    settings: Settings | None = None,
    service: Any | None = None,
) -> InventoryReport:
    settings = settings or get_settings()
    service = service or _get_google_service(settings)

    try:
        response = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.spreadsheet_id,
                range=f"'{settings.worksheet}'!{settings.range_name}",
                valueRenderOption="FORMATTED_VALUE",
            )
            .execute()
        )
    except HttpError as error:
        raise GoogleSheetsError("A consulta à planilha no Google falhou.") from error

    values = response.get("values", [])
    if not values:
        return InventoryReport(columns=[], items=[], values={}, total=0)

    used_keys: set[str] = set()
    columns = [
        Column(key=_json_key(label, index, used_keys), label=label)
        for index, label in enumerate(values[0])
    ]

    items: list[dict[str, str]] = []
    row_values: dict[str, dict[str, str]] = {}
    for spreadsheet_row, row in enumerate(values[1:], start=2):
        padded_row = [str(value) for value in row[: len(columns)]]
        padded_row.extend([""] * (len(columns) - len(padded_row)))
        item = {
            column.key: padded_row[index]
            for index, column in enumerate(columns)
        }
        items.append(item)
        row_values[str(spreadsheet_row)] = item

    return InventoryReport(
        columns=columns,
        items=items,
        values=row_values,
        total=len(items),
    )


app = FastAPI(
    title="Relatório de Auditoria de Inventário",
    version="0.1.0",
    docs_url="/docs",
)


@app.get("/health", tags=["operação"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/auditorias",
    response_model=InventoryReport,
    tags=["auditorias"],
)
def listar_auditorias() -> InventoryReport:
    try:
        return consultar_respostas_inventario()
    except ConfigurationError as error:
        LOGGER.error("Configuração inválida do relatório: %s", error)
        raise HTTPException(status_code=503, detail="Integração ainda não configurada.") from error
    except GoogleSheetsError as error:
        LOGGER.exception("Falha na integração com o Google Sheets.")
        raise HTTPException(status_code=502, detail="Falha ao consultar dados no Google Sheets.") from error
