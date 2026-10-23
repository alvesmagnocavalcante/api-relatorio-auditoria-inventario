from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app import (
    InventoryReport,
    Settings,
    _get_google_service,
    app,
    consultar_respostas_inventario,
)


class InventoryReportTests(TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            spreadsheet_id="spreadsheet-id",
            worksheet="Respostas ao formulário 1",
            range_name="A:AA",
            token_file=Path("token.json"),
        )

    def test_normalizes_headers_and_preserves_duplicate_labels(self) -> None:
        service = Mock()
        (
            service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value
        ) = {
            "values": [
                ["Carimbo de data/hora", "Comentários:", "Comentários:"],
                ["16/10/2026 09:00", "Primeiro", "Segundo"],
            ]
        }

        report = consultar_respostas_inventario(self.settings, service)

        self.assertEqual(
            [column.key for column in report.columns],
            ["carimbo_de_data_hora", "comentarios", "comentarios_2"],
        )
        self.assertEqual(report.total, 1)
        self.assertEqual(report.items[0]["comentarios_2"], "Segundo")
        self.assertEqual(report.values["2"]["comentarios"], "Primeiro")
        self.assertEqual(report.values["2"]["comentarios_2"], "Segundo")
        service.spreadsheets.return_value.values.return_value.get.assert_called_once_with(
            spreadsheetId="spreadsheet-id",
            range="'Respostas ao formulário 1'!A:AA",
            valueRenderOption="FORMATTED_VALUE",
        )

    def test_health_endpoint(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("app.build")
    @patch("app.Credentials.from_authorized_user_info")
    def test_builds_google_service_from_token_json(
        self,
        from_authorized_user_info: Mock,
        build: Mock,
    ) -> None:
        settings = Settings(
            spreadsheet_id="spreadsheet-id",
            worksheet="Respostas ao formulário 1",
            range_name="A:AA",
            token_file=None,
            token_json='{"type":"authorized_user","client_id":"id"}',
        )

        service = _get_google_service(settings)

        self.assertIs(service, build.return_value)
        from_authorized_user_info.assert_called_once_with(
            {"type": "authorized_user", "client_id": "id"},
            ("https://www.googleapis.com/auth/spreadsheets.readonly",),
        )

    def test_auditorias_endpoint_returns_report(self) -> None:
        report = InventoryReport(
            columns=[{"key": "hotel", "label": "Hotel"}],
            items=[{"hotel": "Carmel"}],
            values={"2": {"hotel": "Carmel"}},
            total=1,
        )

        with patch(
            "app.consultar_respostas_inventario",
            return_value=report,
        ):
            with TestClient(app) as client:
                response = client.get("/api/auditorias")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), report.model_dump())
