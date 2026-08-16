import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path


HTML_PATH = Path(__file__).with_name('index_fase4.html')


def inline_script():
    html = HTML_PATH.read_text(encoding='utf-8')
    scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', html, flags=re.DOTALL)
    if len(scripts) != 1:
        raise AssertionError(f'Expected one inline script, found {len(scripts)}')
    return scripts[0]


def run_inline(expression):
    source = inline_script() + '\n' + "globalThis.__exports = { appState, quitarAEISeleccion, normalizarEstadoGuardado, extraerAniosPeriodo, sincronizarPeriodo, normalizarMetaInput, construirPayload, guardarDatos };"
    harness = f"""
const vm = require('vm');
const context = {{
  window: {{ addEventListener() {{}} }},
  localStorage: {{
    values: {{}},
    setItem(key, value) {{ this.values[key] = value; }},
    getItem(key) {{ return this.values[key] || null; }}
  }},
  document: {{
    querySelector() {{ return null; }},
    periodo: '',
    getElementById(id) {{ return id === 'periodo_pei' ? {{ value: this.periodo }} : null; }}
  }},
  console
}};
vm.createContext(context);
vm.runInContext({json.dumps(source)}, context);
const result = vm.runInContext({json.dumps(expression)}, context);
process.stdout.write(JSON.stringify(result));
"""
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node is required for inline JavaScript state tests')
    try:
        completed = subprocess.run(
            [node, '-e', harness],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise AssertionError(error.stderr) from error
    return json.loads(completed.stdout)


class IndexFase4StateTests(unittest.TestCase):
    def test_payload_keeps_original_catalog_codes_and_indicator_ids(self):
        result = run_inline(
            """(() => {
  const { appState, construirPayload } = __exports;
  document.periodo = '2026-2030';
  appState.periodo_pei = '2026-2030';
  appState.selecciones = {
    oei: ['oei-OEI.01', 'oei-OEI.04', 'oei-OEI.10'],
    indicadoresOEI: ['ind-oei-OEI.01-0', 'ind-oei-OEI.04-0', 'ind-oei-OEI.10-0'],
    aei: ['aei-AEI.04.02'],
    indicadoresAEI: ['ind-aei-AEI.04.02-0']
  };
  appState.prioridades = {
    oei: ['OEI.01', 'OEI.04', 'OEI.10'],
    aei: { 'OEI.01': [], 'OEI.04': ['AEI.04.02'], 'OEI.10': [] }
  };
  const payload = construirPayload();
  return { payload, json: JSON.stringify(payload) };
})()"""
        )

        self.assertEqual(result['payload']['selecciones']['oei'], [
            'oei-OEI.01', 'oei-OEI.04', 'oei-OEI.10'
        ])
        self.assertEqual(result['payload']['prioridades']['oei'], [
            'OEI.01', 'OEI.04', 'OEI.10'
        ])
        self.assertEqual(result['payload']['prioridades']['aei']['OEI.04'], ['AEI.04.02'])
        self.assertEqual(json.loads(result['json']), result['payload'])

    def test_negative_input_and_paste_are_clamped_before_state_and_serialization(self):
        result = run_inline(
            """(() => {
  const { appState, normalizarMetaInput, construirPayload, guardarDatos } = __exports;
  const indicatorId = 'ind-oei-OEI.01-0';
  document.periodo = '2026-2030';
  appState.periodo_pei = '2026-2030';
  appState.selecciones = {
    oei: ['oei-OEI.01'],
    indicadoresOEI: [indicatorId],
    aei: [],
    indicadoresAEI: []
  };
  appState.metas = {
    [indicatorId]: { año_base: 2024, valor_base: -2, meta_2026: -3, meta_2028: -5 }
  };
  const manualInput = { id: `${indicatorId}-valor_base`, value: '-4.5' };
  const pastedInput = { id: `${indicatorId}-meta_2026`, value: '-1' };
  const emptyInput = { id: `${indicatorId}-meta_2027`, value: '' };
  normalizarMetaInput(manualInput);
  normalizarMetaInput(pastedInput);
  normalizarMetaInput(emptyInput);
  const payload = construirPayload();
  guardarDatos();
  return {
    manual: manualInput.value,
    pasted: pastedInput.value,
    empty: emptyInput.value,
    state: appState.metas[indicatorId],
    payload: payload.metas[indicatorId],
    stored: JSON.parse(localStorage.values.peiFormData).metas[indicatorId]
  };
})()"""
        )

        self.assertEqual(result['manual'], '0')
        self.assertEqual(result['pasted'], '0')
        self.assertEqual(result['empty'], '')
        for serialized in (result['state'], result['payload'], result['stored']):
            self.assertEqual(serialized['valor_base'], 0)
            self.assertEqual(serialized['meta_2026'], 0)
            self.assertEqual(serialized['meta_2027'], '')
            self.assertEqual(serialized['meta_2028'], 0)
        self.assertEqual(result['state']['año_base'], 2024)

    def test_period_change_clears_old_metas_and_years_are_explicit(self):
        result = run_inline(
            """(() => {
  const { appState, extraerAniosPeriodo, sincronizarPeriodo } = __exports;
  document.periodo = '2026-2030';
  appState.periodo_pei = '2026-2030';
  appState.metas = { 'ind-oei-OEI.01-0': { meta_2026: 10 } };
  document.periodo = '2027-2032';
  const years = sincronizarPeriodo();
  return { years, metas: appState.metas, invalid: extraerAniosPeriodo('') };
})()"""
        )

        self.assertEqual(result['years'], [2027, 2028, 2029, 2030, 2031, 2032])
        self.assertEqual(result['metas'], {})
        self.assertEqual(result['invalid'], [])

    def test_inline_javascript_parses(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is required to parse inline JavaScript')
        completed = subprocess.run(
            [node, '--check'],
            input=inline_script(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_unchecking_collapsed_aei_removes_descendants_from_complete_state(self):
        result = run_inline(
            """(() => {
  const { appState, quitarAEISeleccion } = __exports;
  appState.selecciones = {
    oei: ['oei-OEI.01'],
    indicadoresOEI: ['ind-oei-OEI.01-0'],
    aei: ['aei-AEI.01.01', 'aei-AEI.01.02'],
    indicadoresAEI: ['ind-aei-AEI.01.01-0', 'ind-aei-AEI.01.02-0']
  };
  appState.prioridades = {
    oei: ['OEI.01'],
    aei: { 'OEI.01': ['AEI.01.01', 'AEI.01.02'] }
  };
  appState.metas = {
    'ind-aei-AEI.01.01-0': { meta_2026: 10 },
    'ind-aei-AEI.01.02-0': { meta_2026: 20 }
  };
  quitarAEISeleccion('OEI.01', 'AEI.01.01');
  return { selections: appState.selecciones, priorities: appState.prioridades, metas: appState.metas };
})()"""
        )

        self.assertEqual(result['selections']['aei'], ['aei-AEI.01.02'])
        self.assertEqual(result['selections']['indicadoresAEI'], ['ind-aei-AEI.01.02-0'])
        self.assertEqual(result['priorities']['oei'], ['OEI.01'])
        self.assertEqual(result['priorities']['aei']['OEI.01'], ['AEI.01.02'])
        self.assertNotIn('ind-aei-AEI.01.01-0', result['metas'])
        self.assertIn('ind-aei-AEI.01.02-0', result['metas'])

    def test_restore_normalization_does_not_reintroduce_unselected_aei(self):
        result = run_inline(
            """(() => __exports.normalizarEstadoGuardado({
  selecciones: {
    oei: ['oei-OEI.01'],
    indicadoresOEI: [],
    aei: ['aei-AEI.01.02'],
    indicadoresAEI: ['ind-aei-AEI.01.02-0']
  },
  prioridades: {
    oei: ['OEI.01'],
    aei: { 'OEI.01': ['AEI.01.01', 'AEI.01.02'] }
  },
  metas: {
    'ind-aei-AEI.01.01-0': { meta_2026: 10 },
    'ind-aei-AEI.01.02-0': { meta_2026: 20, meta_2027: 21 }
  }
}))()"""
        )

        self.assertEqual(result['selecciones']['aei'], ['aei-AEI.01.02'])
        self.assertEqual(result['prioridades']['aei']['OEI.01'], ['AEI.01.02'])
        self.assertNotIn('ind-aei-AEI.01.01-0', result['metas'])
        self.assertNotIn('meta_2026', result['metas']['ind-aei-AEI.01.02-0'])

    def test_restore_keeps_selected_oei_priority_when_it_has_no_aei(self):
        result = run_inline(
            """(() => __exports.normalizarEstadoGuardado({
  selecciones: { oei: ['oei-OEI.01'], aei: [], indicadoresOEI: [], indicadoresAEI: [] },
  prioridades: { oei: ['OEI.01'], aei: { 'OEI.01': [] } },
  metas: {}
}))()"""
        )

        self.assertEqual(result['selecciones']['oei'], ['oei-OEI.01'])
        self.assertEqual(result['prioridades']['oei'], ['OEI.01'])
        self.assertEqual(result['prioridades']['aei']['OEI.01'], [])


if __name__ == '__main__':
    unittest.main()
