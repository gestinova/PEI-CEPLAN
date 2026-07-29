#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json, os, sys, re, subprocess

class PEIHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/generar':
            try:
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))
                output = self.generar_documento(data)
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'file': output, 'message': 'Generado'}, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                print(f"ERROR: {e}")
                import traceback; traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass

    def generar_documento(self, data):
        print("\n" + "="*70)
        print("GENERANDO DOCUMENTO PEI")
        print("="*70)

        try:
            from mailmerge import MailMerge
            from docx import Document
            from docx.shared import Pt
            from docx.enum.text import WD_BREAK
            from copy import deepcopy
        except ImportError:
            print("Instalando...")
            subprocess.check_call([sys.executable, "-m", "pip", "install",
                "docx-mailmerge", "python-docx", "--break-system-packages", "--quiet"])
            from mailmerge import MailMerge
            from docx import Document
            from docx.shared import Pt
            from docx.enum.text import WD_BREAK
            from copy import deepcopy

        # Datos
        campos = ['codigo_ue', 'nombre_municipio', 'periodo_pei', 'nombre_provincia',
                  'nombre_region', 'nombre_alcalde', 'resolucion_alcaldia',
                  'plan_desarrollo_concertado', 'ordenanza_pdc', 'mision_institucional',
                  'politica_general_gobierno', 'decreto_politica_general_gobierno']
        d = {k: str(data.get(k, '')).strip() for k in campos}
        print(f"Municipio: {d['nombre_municipio']}")

        # OEI/AEI - Mantener orden de selección
        sel = data.get('selecciones', {})
        oei_list = [x.replace('oei-', '') for x in sel.get('oei', [])]
        aei_list = [x.replace('aei-', '') for x in sel.get('aei', [])]
        
        # Obtener prioridades (orden de selección)
        prioridades = data.get('prioridades', {})
        oei_priorizados = prioridades.get('oei', [])
        
        # Si hay prioridades, usar ese orden; si no, usar orden de selección
        if oei_priorizados:
            oei_ordenados = [x.replace('oei-', '') for x in oei_priorizados if x.replace('oei-', '') in oei_list]
        else:
            oei_ordenados = oei_list
        
        print(f"OEI ordenados: {oei_ordenados}")
        print(f"AEI totales: {len(aei_list)}")

        # Crear orden jerárquico: OEI → sus AEI
        codigos_ordenados = []
        for oei_code in oei_ordenados:
            # Agregar el OEI
            codigos_ordenados.append(oei_code)
            
            # Agregar sus AEI (las que empiecen con el código del OEI)
            # Ej: OEI.01 → AEI.01.01, AEI.01.02, etc.
            oei_num = oei_code.split('.')[1]  # '01' de 'OEI.01'
            aei_de_este_oei = [
                aei for aei in aei_list 
                if aei.startswith(f'AEI.{oei_num}.')
            ]
            # Ordenar AEI por número (AEI.01.01, AEI.01.02, etc.)
            aei_de_este_oei.sort()
            codigos_ordenados.extend(aei_de_este_oei)
        
        print(f"\nOrden de fichas: {codigos_ordenados}")

        # Metas
        metas_raw = data.get('metas', {})
        metas_por_codigo = {}
        for key, meta in metas_raw.items():
            m = re.search(r'ind-oei-(OEI\.\d+)-', key) or re.search(r'ind-aei-(AEI\.\d+\.\d+)-', key)
            if m:
                metas_por_codigo.setdefault(m.group(1), []).append(meta)

        anios_match = re.findall(r'\d{4}', d['periodo_pei'])
        anios = list(range(int(anios_match[0]), int(anios_match[1])+1)) if len(anios_match)>=2 else [2026,2027,2028,2029,2030]

        # PASO 1
        print("\nPASO 1: MailMerge...")
        temp1 = '_temp1.docx'
        merge_data = {
            'Codigo_UE': d['codigo_ue'], 'Nombre_Municipio': d['nombre_municipio'],
            'Periodo_PEI': d['periodo_pei'], 'Nombre_Provincia': d['nombre_provincia'],
            'Nombre_Region': d['nombre_region'], 'Nombre_Alcalde': d['nombre_alcalde'],
            'Resolucion_Alcaldia': d['resolucion_alcaldia'],
            'Plan_Desarrollo_Concertado': d['plan_desarrollo_concertado'],
            'Ordenanza_PDC': d['ordenanza_pdc'], 'Mision_Institucional': d['mision_institucional'],
            'Politica_General_Gobierno': d['politica_general_gobierno'],
            'Decreto_Politica_General_Gobierno': d['decreto_politica_general_gobierno'],
        }
        with MailMerge('PEI_Estandar_-_Informe.docx') as doc:
            doc.merge(**merge_data)
            doc.write(temp1)
        print("  OK")

        # PASO 2
        print("\nPASO 2: Filtrar...")
        doc = Document(temp1)

        # Construir mapa de indices seleccionados por codigo
        ind_oei_sel = sel.get('indicadoresOEI', [])
        ind_aei_sel = sel.get('indicadoresAEI', [])

        indices_oei = {}
        for ind_id in ind_oei_sel:
            m = re.match(r'ind-oei-(OEI\.\d+)-(\d+)', ind_id)
            if m:
                codigo, idx = m.group(1), int(m.group(2))
                indices_oei.setdefault(codigo, set()).add(idx)

        indices_aei = {}
        for ind_id in ind_aei_sel:
            m = re.match(r'ind-aei-(AEI\.\d+\.\d+)-(\d+)', ind_id)
            if m:
                codigo, idx = m.group(1), int(m.group(2))
                indices_aei.setdefault(codigo, set()).add(idx)

        print(f'  Indices OEI: {indices_oei}')
        print(f'  Indices AEI: {indices_aei}')

        def filtrar_tabla(table, patron, lista, indices_map, col_codigo):
            """Filtra filas de una tabla buscando el codigo en una columna especifica."""
            fdel = []
            contadores = {}
            for i, row in enumerate(table.rows):
                if len(row.cells) <= col_codigo:
                    continue
                txt_col = row.cells[col_codigo].text.strip()
                m = re.search(patron, txt_col)
                if m:
                    codigo = m.group()
                    if codigo not in lista:
                        fdel.append(i)
                    else:
                        # Solo filtrar por indice si hay seleccion explicita
                        if codigo in indices_map:
                            idx = contadores.get(codigo, 0)
                            contadores[codigo] = idx + 1
                            if idx not in indices_map[codigo]:
                                fdel.append(i)
            for i in reversed(fdel):
                table._element.remove(table.rows[i]._element)
            return len(fdel)

        def detectar_col(table, patron):
            """Detecta en que columna aparece el patron en una tabla."""
            for row in table.rows[1:4]:
                for c_idx, cell in enumerate(row.cells):
                    if re.search(patron, cell.text.strip()):
                        return c_idx
            return -1

        def filtrar_tabla_combinada(table, col_oei, col_aei):
            """Para tablas como Ruta Estrategica donde cada fila tiene OEI y AEI.
            Se elimina la fila si el OEI NO esta seleccionado O el AEI NO esta seleccionado."""
            fdel = []
            for i, row in enumerate(table.rows):
                ncols = len(row.cells)
                if ncols <= max(col_oei, col_aei):
                    continue
                txt_oei = row.cells[col_oei].text.strip()
                txt_aei = row.cells[col_aei].text.strip()
                m_oei = re.search(r'OEI\.\d{2}', txt_oei)
                m_aei = re.search(r'AEI\.\d{2}\.\d{2}', txt_aei)
                if m_oei or m_aei:
                    oei_ok = (not m_oei) or (m_oei.group() in oei_list)
                    aei_ok = (not m_aei) or (m_aei.group() in aei_list)
                    if not oei_ok or not aei_ok:
                        fdel.append(i)
            for i in reversed(fdel):
                table._element.remove(table.rows[i]._element)
            return len(fdel)

        def es_tabla_matriz(table):
            """Detecta si es la tabla B-3 Matriz PEI: tiene OEI y AEI en col 0
            y filas separadoras de Acciones Estrategicas."""
            for row in table.rows[2:5]:
                if row.cells and re.search(r'OEI\.\d{2}', row.cells[0].text):
                    return True
            return False

        def filtrar_tabla_matriz(table):
            """Filtra la tabla B-3: elimina grupos OEI+separador+AEIs no seleccionados."""
            fdel = []
            oei_activo = False
            contadores_oei = {}
            contadores_aei = {}

            for i, row in enumerate(table.rows):
                if not row.cells:
                    continue
                col0 = row.cells[0].text.strip()

                m_aei = re.search(r'AEI\.\d{2}\.\d{2}', col0)
                m_oei = re.search(r'OEI\.\d{2}', col0)

                # Fila AEI pura
                if m_aei:
                    codigo_aei = m_aei.group()
                    if not oei_activo or codigo_aei not in aei_list:
                        fdel.append(i)
                    else:
                        # Solo filtrar por indice si el usuario selecciono indicadores explicitamente
                        if codigo_aei in indices_aei:
                            idx = contadores_aei.get(codigo_aei, 0)
                            contadores_aei[codigo_aei] = idx + 1
                            if idx not in indices_aei[codigo_aei]:
                                fdel.append(i)

                # Fila separadora "Acciones Estrategicas Institucionales del OEI.XX"
                elif m_oei and len(col0) > 10:
                    if not oei_activo:
                        fdel.append(i)

                # Fila OEI pura (codigo corto como "OEI.02")
                elif m_oei:
                    codigo_oei = m_oei.group()
                    oei_activo = codigo_oei in oei_list
                    if oei_activo:
                        # Solo filtrar por indice si el usuario selecciono indicadores explicitamente
                        if codigo_oei in indices_oei:
                            idx = contadores_oei.get(codigo_oei, 0)
                            contadores_oei[codigo_oei] = idx + 1
                            if idx not in indices_oei[codigo_oei]:
                                fdel.append(i)
                    else:
                        fdel.append(i)

            for i in reversed(fdel):
                table._element.remove(table.rows[i]._element)
            return len(fdel)

        e = 0
        for table in doc.tables:
            col_oei = detectar_col(table, r'OEI\.\d{2}')
            col_aei = detectar_col(table, r'AEI\.\d{2}\.\d{2}')

            if col_oei == 0 and col_aei == 0 and es_tabla_matriz(table):
                # Tabla B-3: OEI y AEI ambos en col 0, con separadores
                e += filtrar_tabla_matriz(table)
            elif col_oei >= 0 and col_aei >= 0 and col_oei != col_aei:
                # Tabla combinada: OEI y AEI en distintas columnas (Ruta Estrategica)
                e += filtrar_tabla_combinada(table, col_oei, col_aei)
            else:
                # Tabla simple: solo OEI o solo AEI
                if col_oei >= 0:
                    e += filtrar_tabla(table, r'OEI\.\d{2}', oei_list, indices_oei, col_oei)
                if col_aei >= 0:
                    e += filtrar_tabla(table, r'AEI\.\d{2}\.\d{2}', aei_list, indices_aei, col_aei)
        print(f"  Filas: {e}")

        # Metas
        def esc(c, t):
            for p in c.paragraphs:
                for r in p.runs: r.text = ''
            if c.paragraphs:
                runs = c.paragraphs[0].runs
                if runs: runs[0].text = str(t)
                else: c.paragraphs[0].add_run(str(t))

        def fmt(v):
            if not v: return ''
            try:
                f = float(v)
                return str(int(f)) if f == int(f) else str(f)
            except: return str(v)

        def get(m, ks):
            for k in ks:
                if k in m and m[k]: return m[k]
            return ''

        mok = 0
        for table in doc.tables:
            cab = ' '.join(c.text for r in table.rows[:2] for c in r.cells)
            if 'Logros Esperados' not in cab: continue
            for row in table.rows:
                cs = row.cells
                if len(cs) < 6: continue
                cod = cs[0].text.strip()
                m = re.match(r'^(OEI\.\d{2}|AEI\.\d{2}\.\d{2})$', cod)
                if not m or m.group() not in metas_por_codigo: continue
                meta = metas_por_codigo[m.group()][0]
                esc(cs[3], fmt(get(meta, ['año_base', 'anio_base'])))
                esc(cs[4], fmt(get(meta, ['valor_base'])))
                for j, a in enumerate(anios):
                    if 5+j < len(cs):
                        esc(cs[5+j], fmt(get(meta, [f'meta_{a}'])))
                mok += 1
        print(f"  Metas: {mok}")
        doc.save(temp1)

        # PASO 3: Fichas EN ORDEN JERÁRQUICO
        print("\nPASO 3: Fichas (orden jerárquico)...")
        with open('fichas_tecnicas.json', 'r', encoding='utf-8') as f:
            fichas_db = json.load(f)

        doc_base = Document(temp1)
        
        # Salto y título
        p = doc_base.add_paragraph()
        p.add_run().add_break(WD_BREAK.PAGE)
        pt = doc_base.add_paragraph()
        rt = pt.add_run("ANEXO A - 6: FICHA TÉCNICA DE INDICADORES")
        rt.bold = True
        rt.font.size = Pt(12)

        # Plantilla
        doc_plt = Document('Plantilla_de_ficha_técnica.docx')
        tbl_plt = doc_plt.tables[0]

        fg = 0
        # USAR ORDEN JERÁRQUICO
        for codigo in codigos_ordenados:
            if codigo not in fichas_db: 
                print(f"  Aviso: {codigo} no tiene ficha en JSON")
                continue
            
            ficha = fichas_db[codigo][0]
            
            # Salto antes (excepto primera)
            if fg > 0:
                px = doc_base.add_paragraph()
                px.add_run().add_break(WD_BREAK.PAGE)
            
            # Copiar tabla
            nt = deepcopy(tbl_plt._element)
            doc_base.element.body.append(nt)
            tb = doc_base.tables[-1]
            
            # Llenar datos
            def stxt(ri, ci, v):
                if ri < len(tb.rows) and ci < len(tb.rows[ri].cells):
                    cell = tb.rows[ri].cells[ci]
                    for para in cell.paragraphs:
                        for run in para.runs:
                            run.text = ''
                    if cell.paragraphs:
                        if cell.paragraphs[0].runs:
                            cell.paragraphs[0].runs[0].text = str(v)
                        else:
                            cell.paragraphs[0].add_run(str(v))
            
            stxt(1, 1, ficha.get('objetivo_accion', ''))
            stxt(2, 1, ficha.get('nombre_indicador', ''))
            stxt(3, 1, ficha.get('justificacion', ''))
            stxt(4, 1, ficha.get('responsables', ''))
            stxt(5, 1, ficha.get('limitaciones', ''))
            stxt(6, 1, ficha.get('metodo_calculo', ''))
            stxt(7, 1, ficha.get('sentido_esperado', ''))
            stxt(8, 1, ficha.get('proceso_recoleccion', ''))
            stxt(9, 1, ficha.get('fuente_datos', ''))
            stxt(11, 1, ficha.get('anio_base', ''))
            stxt(12, 1, ficha.get('valor_relativo', ''))
            stxt(13, 1, ficha.get('valor_absoluto', ''))
            
            fg += 1
            print(f"  {fg}. {codigo}")

        print(f"\nTotal fichas generadas: {fg}")

        output = f"PEI_{d['nombre_municipio'].replace(' ', '_') or 'Doc'}.docx"
        doc_base.save(output)
        if os.path.exists(temp1): os.remove(temp1)

        print(f"\nGENERADO: {output}")
        print("="*70)
        return output

httpd = HTTPServer(('', 8000), PEIHandler)
print("\n" + "="*70)
print("  GENERADOR PEI - ORDEN JERÁRQUICO")
print("  http://localhost:8000")
print("="*70 + "\n")
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\nDetenido.")
