import http.client
import json
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import patch

import catalogo_ue
from generador_pei_fase4 import PEIHandler


class FakeWorksheet:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True):
        return iter(self._rows)


class FakeWorkbook:
    def __init__(self, sheets):
        self._sheets = sheets
        self.sheetnames = list(sheets)

    def __getitem__(self, sheet_name):
        return self._sheets[sheet_name]

    def close(self):
        pass


def fake_workbook():
    return FakeWorkbook({
        'IT PEI': FakeWorksheet([
            ['Id_UE', 'Nombre_unidad_ejecutora', 'nombre_provincia', 'nombre_departamento', 'Periodo PEI'],
            [300682, 'Municipalidad A', 'Provincia A', 'Region A', '2024-2028'],
        ]),
        'Data_UEs': FakeWorksheet([
            ['Id_UE', 'Nombre_unidad_ejecutora', 'nombre_provincia', 'nombre_departamento', 'Ult.PEI'],
            ['300682.0', 'Municipalidad A actualizada', 'Provincia A', 'Region A', '2025-2029'],
            ['300683', 'Municipalidad B', 'Provincia B', 'Region B', None],
        ]),
    })


class CatalogoLoaderTests(unittest.TestCase):
    def tearDown(self):
        catalogo_ue.limpiar_cache_catalogo_ues()

    def test_loads_both_sheets_and_returns_public_fields(self):
        with NamedTemporaryFile(suffix='.xlsx') as excel_file:
            with patch.object(catalogo_ue, '_load_workbook', return_value=fake_workbook()):
                catalog = catalogo_ue.cargar_catalogo_ues(excel_file.name)

        self.assertEqual(catalog['300682']['nombre_municipio'], 'Municipalidad A actualizada')
        self.assertEqual(catalog['300682']['periodo_pei'], '2025-2029')
        self.assertEqual(set(catalog['300683']), {
            'codigo_ue',
            'nombre_municipio',
            'nombre_provincia',
            'nombre_region',
            'periodo_pei',
        })

    def test_absent_file_returns_empty_catalog_without_importing_excel(self):
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / 'IT_PEI.xlsx'
            catalogo_ue.limpiar_cache_catalogo_ues()
            with patch.object(catalogo_ue, '_load_workbook') as loader:
                self.assertEqual(catalogo_ue.cargar_catalogo_ues(missing), {})
            loader.assert_not_called()

    def test_malformed_workbook_raises_catalog_error(self):
        malformed = FakeWorkbook({'IT PEI': FakeWorksheet([['Id_UE']])})
        with NamedTemporaryFile(suffix='.xlsx') as excel_file:
            with patch.object(catalogo_ue, '_load_workbook', return_value=malformed):
                with self.assertRaises(catalogo_ue.CatalogoUEError):
                    catalogo_ue.cargar_catalogo_ues(excel_file.name)


class EndpointTests(unittest.TestCase):
    def request(self, path, method='GET', body=None, headers=None):
        server = HTTPServer(('127.0.0.1', 0), PEIHandler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        connection = http.client.HTTPConnection(*server.server_address)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        body = json.loads(response.read().decode('utf-8'))
        connection.close()
        thread.join(timeout=2)
        server.server_close()
        return response.status, body

    def test_valid_id_returns_catalog_data(self):
        with patch('generador_pei_fase4.obtener_ue', return_value={
            'codigo_ue': '300682',
            'nombre_municipio': 'Municipalidad A',
            'nombre_provincia': 'Provincia A',
            'nombre_region': 'Region A',
            'periodo_pei': '2025-2029',
        }):
            status, body = self.request('/api/ue/300682')

        self.assertEqual(status, 200)
        self.assertTrue(body['success'])
        self.assertEqual(body['data']['codigo_ue'], '300682')

    def test_invalid_id_returns_bad_request(self):
        status, body = self.request('/api/ue/../../generador_pei_fase4.py')

        self.assertEqual(status, 400)
        self.assertEqual(body['error']['code'], 'invalid_id')

    def test_missing_id_returns_not_found(self):
        with patch('generador_pei_fase4.obtener_ue', return_value=None):
            status, body = self.request('/api/ue/999999')

        self.assertEqual(status, 404)
        self.assertEqual(body['error']['code'], 'ue_not_found')

    def test_catalog_failure_returns_generic_server_error(self):
        with patch('generador_pei_fase4.obtener_ue', side_effect=catalogo_ue.CatalogoUEError('details')):
            status, body = self.request('/api/ue/300682')

        self.assertEqual(status, 500)
        self.assertEqual(body['error']['code'], 'internal_error')
        self.assertNotIn('details', json.dumps(body))

    def test_generate_endpoint_is_not_intercepted_by_catalog_route(self):
        with patch('generador_pei_fase4.validar_payload', return_value={}), \
                patch.object(PEIHandler, 'generar_documento', return_value='PEI_Test.docx'):
            status, body = self.request(
                '/generar',
                method='POST',
                body='{}',
                headers={'Content-Type': 'application/json'},
            )

        self.assertEqual(status, 200)
        self.assertTrue(body['success'])
        self.assertEqual(body['file'], 'PEI_Test.docx')

    def test_generate_rejects_negative_meta_before_docx(self):
        payload = {
            'periodo_pei': '2027-2032',
            'ordenanza_pdc': '002-2024-MDL',
            'selecciones': {
                'oei': ['oei-OEI.01'],
                'aei': ['aei-AEI.01.01'],
                'indicadoresOEI': ['ind-oei-OEI.01-0'],
                'indicadoresAEI': ['ind-aei-AEI.01.01-0'],
            },
            'prioridades': {
                'oei': ['OEI.01'],
                'aei': {'OEI.01': ['AEI.01.01']},
            },
            'metas': {
                'ind-oei-OEI.01-0': {'valor_base': -1},
            },
        }
        with patch.object(PEIHandler, 'generar_documento') as generate:
            status, body = self.request(
                '/generar',
                method='POST',
                body=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
            )

        self.assertEqual(status, 422)
        self.assertFalse(body['success'])
        self.assertIsInstance(body['details'], list)
        self.assertIn('negative_value', {error['code'] for error in body['details']})
        generate.assert_not_called()

    def test_generate_rejects_unsupported_content_type(self):
        with patch.object(PEIHandler, 'generar_documento') as generate:
            status, body = self.request(
                '/generar',
                method='POST',
                body='{}',
                headers={'Content-Type': 'text/plain'},
            )

        self.assertEqual(status, 415)
        self.assertEqual(body['details'][0]['code'], 'unsupported_media_type')
        generate.assert_not_called()

    def test_generate_rejects_oversized_content_length(self):
        with patch.object(PEIHandler, 'generar_documento') as generate:
            status, body = self.request(
                '/generar',
                method='POST',
                body='{}',
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(1024 * 1024 + 1),
                },
            )

        self.assertEqual(status, 413)
        self.assertEqual(body['details'][0]['code'], 'payload_too_large')
        generate.assert_not_called()

    def test_generate_internal_error_does_not_leak_traceback(self):
        with patch('generador_pei_fase4.validar_payload', return_value={}), \
                patch.object(PEIHandler, 'generar_documento', side_effect=RuntimeError('secret details')):
            status, body = self.request(
                '/generar',
                method='POST',
                body='{}',
                headers={'Content-Type': 'application/json'},
            )

        self.assertEqual(status, 500)
        self.assertEqual(body['error'], 'Error interno del servidor.')
        self.assertNotIn('secret details', json.dumps(body))
        self.assertNotIn('Traceback', json.dumps(body))


if __name__ == '__main__':
    unittest.main()
