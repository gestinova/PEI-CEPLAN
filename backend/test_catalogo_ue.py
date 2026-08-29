import http.client
import json
import os
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import patch

import catalogo_ue
import generador_pei_fase4
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

    def test_relative_configured_path_is_resolved_from_project_root(self):
        with patch.dict(os.environ, {catalogo_ue.CATALOGO_UE_ENV: 'IT_PEI.xlsx'}):
            self.assertEqual(
                catalogo_ue.resolver_ruta_catalogo(),
                catalogo_ue.PROJECT_ROOT / 'IT_PEI.xlsx',
            )


class EndpointTests(unittest.TestCase):
    def request_raw(self, path, method='GET', body=None, headers=None):
        server = HTTPServer(('127.0.0.1', 0), PEIHandler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        connection = http.client.HTTPConnection(*server.server_address)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        response_status = response.status
        response_headers = dict(response.getheaders())
        response_body = response.read()
        connection.close()
        thread.join(timeout=2)
        server.server_close()
        return response_status, response_headers, response_body

    def request(self, path, method='GET', body=None, headers=None):
        status, _, response_body = self.request_raw(path, method, body, headers)
        return status, json.loads(response_body.decode('utf-8'))

    def test_root_serves_the_active_frontend_entrypoint(self):
        status, headers, body = self.request_raw('/')

        self.assertEqual(status, 200)
        self.assertIn('text/html', headers.get('Content-Type', headers.get('Content-type', '')))
        self.assertIn(b'<title>Generador de Documentos PEI', body)

    def test_head_serves_allowed_public_files_without_body(self):
        for path in ('/', '/index.html', '/matriz_estandar.json'):
            with self.subTest(path=path):
                status, headers, body = self.request_raw(path, method='HEAD')

                self.assertEqual(status, 200)
                self.assertEqual(body, b'')
                self.assertGreater(int(headers['Content-Length']), 0)

    def test_head_blocks_internal_and_traversal_paths_without_creating_outputs(self):
        before = sorted(path.name for path in generador_pei_fase4.ARCHIVOS_GEN_DIR.iterdir())
        blocked_paths = (
            '/generador_pei_fase4.py',
            '/backend/generador_pei_fase4.py',
            '/backend/fichas_tecnicas.json',
            '/plantillas/PEI_Estandar_-_Informe.docx',
            '/IT_PEI.xlsx',
            '/archivos-gen/interno.docx',
            '/../backend/generador_pei_fase4.py',
            '/%2e%2e/backend/generador_pei_fase4.py',
            '/../archivos-gen/interno.docx',
        )

        for path in blocked_paths:
            with self.subTest(path=path):
                status, _, body = self.request_raw(path, method='HEAD')

                self.assertEqual(status, 404)
                self.assertEqual(body, b'')

        after = sorted(path.name for path in generador_pei_fase4.ARCHIVOS_GEN_DIR.iterdir())
        self.assertEqual(after, before)

    def test_options_allows_only_the_configured_origin(self):
        with patch.dict(os.environ, {'PEI_ALLOWED_ORIGIN': 'https://pei.example'}):
            denied_status, denied_headers, denied_body = self.request_raw(
                '/generar',
                method='OPTIONS',
                headers={
                    'Origin': 'https://other.example',
                    'Access-Control-Request-Method': 'POST',
                },
            )
            allowed_status, allowed_headers, _ = self.request_raw(
                '/generar',
                method='OPTIONS',
                headers={
                    'Origin': 'https://pei.example',
                    'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'Content-Type',
                },
            )

        self.assertEqual(denied_status, 403)
        self.assertNotIn('Access-Control-Allow-Origin', denied_headers)
        self.assertEqual(json.loads(denied_body)['error']['code'], 'cors_origin_not_allowed')
        self.assertEqual(allowed_status, 204)
        self.assertEqual(allowed_headers['Access-Control-Allow-Origin'], 'https://pei.example')
        self.assertEqual(allowed_headers['Access-Control-Allow-Methods'], 'GET, POST, OPTIONS')
        self.assertEqual(allowed_headers['Access-Control-Allow-Headers'], 'Content-Type')
        self.assertNotEqual(allowed_headers['Access-Control-Allow-Origin'], '*')

    def test_matrix_get_includes_cors_only_for_the_configured_origin(self):
        with patch.dict(os.environ, {'PEI_ALLOWED_ORIGIN': 'https://pei.example'}):
            allowed_status, allowed_headers, allowed_body = self.request_raw(
                '/matriz_estandar.json',
                headers={'Origin': 'https://pei.example'},
            )
            denied_status, denied_headers, _ = self.request_raw(
                '/matriz_estandar.json',
                headers={'Origin': 'https://other.example'},
            )
            same_origin_status, same_origin_headers, _ = self.request_raw(
                '/matriz_estandar.json',
            )

        self.assertEqual(allowed_status, 200)
        self.assertTrue(json.loads(allowed_body)['oei'])
        self.assertEqual(allowed_headers['Access-Control-Allow-Origin'], 'https://pei.example')
        self.assertEqual(allowed_headers['Vary'], 'Origin')
        self.assertEqual(denied_status, 200)
        self.assertNotIn('Access-Control-Allow-Origin', denied_headers)
        self.assertEqual(same_origin_status, 200)
        self.assertNotIn('Access-Control-Allow-Origin', same_origin_headers)

    def test_json_api_response_includes_cors_for_the_configured_origin(self):
        with patch.dict(os.environ, {'PEI_ALLOWED_ORIGIN': 'https://pei.example'}), \
                patch('generador_pei_fase4.obtener_ue', return_value=None):
            status, headers, body = self.request_raw(
                '/api/ue/999999',
                headers={'Origin': 'https://pei.example'},
            )

        self.assertEqual(status, 404)
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'https://pei.example')
        self.assertEqual(json.loads(body)['error']['code'], 'ue_not_found')

    def test_wildcard_cors_configuration_does_not_emit_wildcard_headers(self):
        with patch.dict(os.environ, {'PEI_ALLOWED_ORIGIN': '*'}):
            status, headers, _ = self.request_raw(
                '/matriz_estandar.json',
                headers={'Origin': 'https://pei.example'},
            )

        self.assertEqual(status, 200)
        self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_generate_returns_json_and_download_route_returns_docx(self):
        payload = {
            'codigo_ue': '150101',
            'nombre_municipio': 'Municipio Prueba',
            'periodo_pei': '2026-2030',
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
        }
        filename = 'PEI_Municipio_Prueba.docx'

        with TemporaryDirectory() as temp_dir:
            generated_dir = Path(temp_dir)
            (generated_dir / filename).write_bytes(b'PK\x03\x04fake-docx')
            with patch('generador_pei_fase4.ARCHIVOS_GEN_DIR', generated_dir), \
                    patch.object(PEIHandler, 'generar_documento', return_value=filename):
                post_status, post_headers, post_body = self.request_raw(
                    '/generar',
                    method='POST',
                    body=json.dumps(payload),
                    headers={'Content-Type': 'application/json'},
                )
                download_status, download_headers, download_body = self.request_raw(
                    f'/downloads/{filename}',
                )

        result = json.loads(post_body.decode('utf-8'))
        self.assertEqual(post_status, 200)
        self.assertIn('application/json', post_headers.get('Content-Type', post_headers.get('Content-type', '')))
        self.assertEqual(result, {
            'success': True,
            'file': filename,
            'message': 'Generado',
        })
        self.assertEqual(download_status, 200)
        self.assertEqual(
            download_headers['Content-Type'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        self.assertEqual(download_body, b'PK\x03\x04fake-docx')

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
