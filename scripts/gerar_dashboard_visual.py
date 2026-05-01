#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path('/Users/leandrobosaipo/Projetos/Arq')
ANALYSES_DIR = BASE / 'Analises'
SOURCE_CSV = BASE / '_trabalho' / 'entregaveis' / 'matriz_pendencias_extraidas.csv'
PUBLIC_DIR = BASE / '_trabalho' / 'pages-public'
PREVIEW_DIR = PUBLIC_DIR / 'assets' / 'previews'
FULL_PREVIEW_DIR = PUBLIC_DIR / 'assets' / 'previews-full'
WORK_PREVIEW_DIR = BASE / '_trabalho' / '_previews_work'
CLASSIFIED_CSV = PUBLIC_DIR / 'classificacao_operacional.csv'
DATA_JSON = PUBLIC_DIR / 'dashboard_data.json'
INDEX_HTML = PUBLIC_DIR / 'index.html'
LEGACY_HTML = PUBLIC_DIR / 'dashboard_escolas.html'

OPEN_STATUSES = {'', 'aberto', 'em_execucao', 'bloqueado', 'revisao_interna'}
PRIO_ORDER = {'P1': 0, 'P2': 1, 'P3': 2, '': 9}
COMPLEXITY_ORDER = {'E4 bloqueado': 0, 'E3 alto': 1, 'E2 médio': 2, 'E1 rápido': 3}

DISCIPLINE_RULES = [
    ('eletrica', ['elétrica', 'eletrica', 'spda', 'aterramento', 'disjuntor', 'quadro de distribuição', 'unifilar', 'multifilar', 'lógica', 'logica', 'cftv']),
    ('hidrossanitario', ['hidráulica', 'hidraulica', 'hidrossanit', 'esgoto', 'drenagem', 'gás', 'gas', 'pluvial', 'reservatório', 'reservatorio', 'bomba']),
    ('estrutura', ['estrutura', 'fundação', 'fundacao', 'sapata', 'estaca', 'pilar', 'viga', 'laje', 'armadura', 'concreto', 'pórtico', 'portico', 'muro de arrimo', 'geotecnia', 'sondagem']),
    ('topografia', ['topografia', 'planialtimétrico', 'planialtimetrico', 'coordenadas', 'terraplenagem', 'levantamento técnico', 'levantamento tecnico']),
    ('arquitetura', ['arquitetura', 'implantação', 'implantacao', 'acessibilidade', 'piso tátil', 'piso tatil', 'rampa', 'corrimão', 'corrimao', 'guarda-corpo', 'cobertura', 'quadra', 'prancha', 'carimbo', 'legenda', 'cota', 'nível', 'nivel', 'terreno', 'fachada', 'vestiário', 'vestiario', 'paisagismo']),
]

TYPE_RULES = [
    ('documental', ['não apresentado', 'nao apresentado', 'item não apresentado', 'item nao apresentado', 'não foi encaminhado', 'nao foi encaminhado', 'art', 'rrt', 'assinado', 'memorial', 'relatório', 'relatorio', 'documento', 'licença', 'licenca', 'alvará', 'alvara']),
    ('gráfico/prancha', ['legenda', 'carimbo', 'prancha', 'representação gráfica', 'representacao grafica', 'sobreposição', 'sobreposicao', 'ilegível', 'ilegiv', 'escala', 'mapa chave', 'mapa de localização', 'mapa de localizacao', 'cotas']),
    ('modelagem', ['compatibilizar', 'incompatível', 'incompativel', 'conflito', 'locar', 'inserir', 'representar', 'ajustar', 'reposicionar', 'conectar', 'substituir']),
    ('normativo', ['nbr', '9050', '8036', 'altura mínima', 'altura minima', 'atende', 'norma', 'legislação', 'legislacao', 'acessibilidade']),
    ('orçamento', ['planilha', 'orçament', 'orcament', 'composição', 'composicao', 'cotações', 'cotacoes', 'quantitativa', 'custos']),
    ('coordenação externa', ['gestão', 'gestao', 'secretaria', 'solicitar', 'justificar', 'qual a', 'como se dará', 'como se dara', 'aprovado pela gestão', 'aprovado pela gestao']),
]

OWNER_RULES = [
    ('coordenação/documentação', ['art', 'rrt', 'licença', 'licenca', 'alvará', 'alvara', 'assinado', 'não foi encaminhado', 'nao foi encaminhado', 'não apresentado', 'nao apresentado', 'documento', 'memorial', 'gestão', 'gestao', 'secretaria']),
    ('arquitetura', ['arquitetura', 'implantação', 'implantacao', 'acessibilidade', 'piso tátil', 'piso tatil', 'rampa', 'corrimão', 'corrimao', 'guarda-corpo', 'cobertura', 'quadra', 'prancha', 'carimbo', 'legenda', 'cota', 'nível', 'nivel', 'terreno']),
    ('estrutura', ['estrutura', 'fundação', 'fundacao', 'sapata', 'estaca', 'pilar', 'viga', 'laje', 'armadura', 'concreto', 'pórtico', 'portico', 'muro de arrimo', 'geotecnia', 'sondagem']),
    ('elétrica', ['elétrica', 'eletrica', 'spda', 'aterramento', 'disjuntor', 'eletroduto', 'quadro de distribuição', 'cargas', 'unifilar', 'multifilar', 'lógica', 'logica', 'cftv']),
    ('hidrossanitário', ['hidráulica', 'hidraulica', 'hidrossanit', 'água', 'agua', 'esgoto', 'drenagem', 'gás', 'gas', 'bomba', 'reservatório', 'reservatorio', 'pluvial', 'calha']),
    ('orçamento', ['orçament', 'orcament', 'planilha', 'composição', 'composicao', 'cotação', 'cotacao', 'quantitativa', 'custos']),
]

PACKAGE_RULES = [
    ('licenças/TRP', ['licença', 'licenca', 'alvará', 'alvara', 'trp', 'termo de recebimento provisório', 'termo de recebimento provisorio']),
    ('documentos assinados', ['art', 'rrt', 'assinado', 'documento', 'memorial', 'relatório', 'relatorio', 'não foi encaminhado', 'nao foi encaminhado', 'não apresentado', 'nao apresentado']),
    ('implantação/topografia', ['implantação', 'implantacao', 'terreno', 'perímetro', 'perimetro', 'área do terreno', 'area do terreno', 'coordenadas', 'locação', 'locacao', 'planialtimétrico', 'planialtimetrico', 'terraplenagem', 'sondagem', 'talude']),
    ('acessibilidade', ['acessibilidade', 'piso tátil', 'piso tatil', 'rampa', 'corrimão', 'corrimao', 'guarda-corpo', 'nbr 9050', 'pcd']),
    ('cobertura/quadra', ['cobertura', 'quadra', 'telhado', 'rufo', 'calha', 'pergolado', 'vestiário', 'vestiario', 'piscina']),
    ('instalações', ['elétrica', 'eletrica', 'hidráulica', 'hidraulica', 'spda', 'incêndio', 'incendio', 'climatização', 'climatizacao', 'lógica', 'logica', 'gás', 'gas', 'cftv', 'drenagem']),
    ('estrutura', ['estrutura', 'fundação', 'fundacao', 'sapata', 'viga', 'pilar', 'laje', 'armadura', 'concreto', 'pórtico', 'portico']),
    ('orçamento/executivo', ['planilha', 'orçament', 'orcament', 'composição', 'composicao', 'cotações', 'cotacoes', 'executivo', 'quantitativa']),
]

ACTION_RULES = [
    ('pedir decisão', ['qual a', 'como se dará', 'como se dara', 'solicitar', 'gestão', 'gestao', 'secretaria', 'justificar']),
    ('apresentar documento', ['não apresentado', 'nao apresentado', 'item não apresentado', 'item nao apresentado', 'não foi encaminhado', 'nao foi encaminhado', 'assinado', 'art', 'rrt', 'memorial', 'relatório', 'relatorio', 'licença', 'licenca', 'alvará', 'alvara']),
    ('compatibilizar modelo', ['compatibilizar', 'incompatível', 'incompativel', 'conflito', 'locar', 'reposicionar', 'conectar', 'ajustar']),
    ('corrigir prancha', ['legenda', 'carimbo', 'prancha', 'mapa', 'escala', 'sobreposição', 'sobreposicao', 'ilegível', 'ilegiv', 'representação gráfica', 'representacao grafica', 'cotas']),
    ('revisar norma', ['nbr', '9050', '8036', 'norma', 'acessibilidade', 'altura mínima', 'altura minima']),
    ('revisar orçamento', ['planilha', 'orçament', 'orcament', 'composição', 'composicao', 'cotação', 'cotacao', 'quantitativa']),
]


def normalize_spaces(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '').strip())


def clean_laudo_text(value: str) -> str:
    text = normalize_spaces(value)
    text = re.sub(r'\bPROJ\.\s*', '', text, flags=re.I)
    text = re.sub(r'\b(DESENHO|TABELA|MODELO 3D EM|ORGANIZAÇÃO)\b', '', text, flags=re.I)
    text = re.sub(r'\b(BÁSICO|BASICO|EXECUTIVO|N/A)\b', '', text, flags=re.I)
    text = re.sub(r'\bNÃO\b', '', text, flags=re.I)
    text = re.sub(r'Página\s+\d+\s+de\s+\d+', '', text, flags=re.I)
    text = re.sub(r'\bSEDUC[A-Z0-9]+\b', '', text, flags=re.I)
    text = re.sub(r'\s+([.,;:])', r'\1', text)
    text = normalize_spaces(text)
    return text or normalize_spaces(value)


def norm_status(value: str) -> str:
    return 'NAO' if value == 'NÃO' else (value or '').strip()


def short_school(name: str) -> str:
    parts = (name or '').replace('ASS', '').replace('JUNT - ', '').replace('001-2026 - ', '').replace('001-2025 - ', '').replace('01-2026 - ', '').strip()
    return parts.replace('1° PARECER_', '').strip()


def canonical_key(value: str) -> str:
    text = unicodedata.normalize('NFKD', value or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def match_first(text: str, rules, default: str) -> str:
    for name, terms in rules:
        if any(term in text for term in terms):
            return name
    return default


def match_all(text: str, rules, default: str):
    hits = [name for name, terms in rules if any(term in text for term in terms)]
    return hits or [default]


def estimate_page(line_text: str, max_pages: int) -> int:
    try:
        line = int(str(line_text).strip())
    except ValueError:
        return 1
    # empiric mapping from extracted text lines to page index range
    return max(1, min(max_pages, int((line / 65.0) + 1)))


def parse_pdf_pages(pdf_path: Path) -> int:
    proc = subprocess.run(['pdfinfo', str(pdf_path)], capture_output=True, text=True, check=False)
    pages = 1
    for line in proc.stdout.splitlines():
        if line.startswith('Pages:'):
            try:
                pages = int(line.split(':', 1)[1].strip())
            except ValueError:
                pages = 1
    return pages


def build_image_index():
    image_index = defaultdict(list)
    pdf_page_count = {}
    WORK_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    FULL_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    for pdf in sorted(ANALYSES_DIR.glob('*.pdf')):
        laudo = pdf.stem
        ckey = canonical_key(laudo)
        pages = parse_pdf_pages(pdf)
        pdf_page_count[ckey] = pages

        # page image map via pdfimages list
        proc = subprocess.run(['pdfimages', '-list', str(pdf)], capture_output=True, text=True, check=False)
        page_has_image = defaultdict(bool)
        for line in proc.stdout.splitlines():
            s = line.strip()
            if not s or s.startswith('page') or s.startswith('-'):
                continue
            parts = s.split()
            if len(parts) < 2:
                continue
            try:
                page = int(parts[0])
                width = int(parts[3]) if len(parts) > 4 else 0
                height = int(parts[4]) if len(parts) > 5 else 0
            except ValueError:
                continue
            if width >= 180 and height >= 120:
                page_has_image[page] = True

        # create per-page preview for pages with images, fallback first pages
        candidate_pages = sorted(page_has_image.keys())
        if not candidate_pages:
            candidate_pages = list(range(1, min(pages, 12) + 1))

        for page in candidate_pages:
            out_base = WORK_PREVIEW_DIR / f"{laudo}__p{page:03d}"
            full_out_base = WORK_PREVIEW_DIR / f"{laudo}__p{page:03d}__full"
            thumb_name = f"{laudo}__p{page:03d}.jpg"
            full_name = f"{laudo}__p{page:03d}__full.jpg"
            thumb_rel = f"assets/previews/{thumb_name}"
            full_rel = f"assets/previews-full/{full_name}"
            thumb_path = PREVIEW_DIR / thumb_name
            full_path = FULL_PREVIEW_DIR / full_name
            if not thumb_path.exists():
                cmd = [
                    'pdftoppm',
                    '-f', str(page),
                    '-singlefile',
                    '-scale-to-x', '420',
                    '-scale-to-y', '320',
                    '-jpeg',
                    str(pdf),
                    str(out_base),
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=False)
                jpg_tmp = out_base.with_suffix('.jpg')
                if jpg_tmp.exists():
                    shutil.move(str(jpg_tmp), str(thumb_path))

            if not full_path.exists():
                cmd = [
                    'pdftoppm',
                    '-f', str(page),
                    '-singlefile',
                    '-scale-to-x', '2200',
                    '-scale-to-y', '-1',
                    '-jpeg',
                    '-jpegopt', 'quality=92,progressive=y,optimize=y',
                    str(pdf),
                    str(full_out_base),
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=False)
                jpg_tmp = full_out_base.with_suffix('.jpg')
                if jpg_tmp.exists():
                    shutil.move(str(jpg_tmp), str(full_path))

            if thumb_path.exists():
                image_index[ckey].append({
                    'page': page,
                    'relpath': thumb_rel,
                    'full_relpath': full_rel if full_path.exists() else thumb_rel,
                    'confidence': 'alta' if page_has_image.get(page, False) else 'baixa',
                    'origin_pdf': laudo,
                })

    # placeholder (public)
    placeholder = PREVIEW_DIR / 'sem_imagem.svg'
    if not placeholder.exists():
        placeholder.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="320">'
            '<rect width="100%" height="100%" fill="#efe7d6"/>'
            '<text x="50%" y="48%" dominant-baseline="middle" text-anchor="middle" '
            'font-family="Trebuchet MS" font-size="22" fill="#7b756a">Sem recorte util</text>'
            '<text x="50%" y="58%" dominant-baseline="middle" text-anchor="middle" '
            'font-family="Trebuchet MS" font-size="15" fill="#8d867a">Revise manualmente no laudo</text>'
            '</svg>',
            encoding='utf-8',
        )

    full_placeholder = FULL_PREVIEW_DIR / 'sem_imagem.svg'
    if not full_placeholder.exists():
        shutil.copyfile(placeholder, full_placeholder)

    return image_index, pdf_page_count


def choose_image(laudo: str, line_text: str, image_index, page_count: int):
    ckey = canonical_key(laudo)
    pages = image_index.get(ckey, [])
    if not pages:
        return 'assets/previews/sem_imagem.svg', 'assets/previews-full/sem_imagem.svg', laudo, 0, 'sem_imagem'

    target = estimate_page(line_text, page_count)
    best = min(pages, key=lambda x: abs(x['page'] - target))
    delta = abs(best['page'] - target)
    conf = best['confidence']
    if delta <= 1:
        conf = 'alta'
    elif delta <= 4 and conf != 'sem_imagem':
        conf = 'media'
    else:
        conf = 'baixa'
    return best['relpath'], best.get('full_relpath', best['relpath']), best.get('origin_pdf', laudo), best['page'], conf


def build_action_text(action: str, discipline: str, text: str):
    if action == 'apresentar documento':
        return 'Juntar e anexar o documento faltante no pacote da disciplina com assinatura e identificação técnica.'
    if action == 'corrigir prancha':
        return 'Ajustar prancha (carimbo, legenda, cotas, representação, mapa) e republicar revisão da folha.'
    if action == 'compatibilizar modelo':
        return 'Compatibilizar elementos em conflito entre plantas, cortes e implantação antes da emissão.'
    if action == 'revisar norma':
        return 'Revisar item normativo aplicável, ajustar solução e atualizar referência técnica no memorial/prancha.'
    if action == 'revisar orçamento':
        return 'Atualizar quantitativos e composição no orçamento para alinhar com o projeto corrigido.'
    if action == 'pedir decisão':
        return 'Registrar pendência de decisão externa e abrir solicitação formal para validação da secretaria/gestão.'
    return 'Fazer triagem técnica e definir ação objetiva para fechar o apontamento.'


def build_revit_steps(discipline: str, action: str):
    if discipline == 'arquitetura':
        return 'No Revit 2025: abra a vista da prancha afetada, ajuste cotas/legenda/carimbo, valide em planta+corte e reexporte PDF da revisão.'
    if discipline == 'estrutura':
        return 'No Revit 2025: revise vistas estruturais, verifique host/níveis e inconsistências entre detalhamento e implantação, depois reemitir folhas estruturais.'
    if discipline == 'eletrica':
        return 'No Revit 2025: revisar família/circuito/quadro, conferir legendas e locação em prancha, e exportar atualização de instalações elétricas.'
    if discipline == 'hidrossanitario':
        return 'No Revit 2025: conferir rede e pontos de drenagem/água/esgoto, ajustar representação em planta e cortes, e emitir revisão das folhas.'
    if discipline == 'topografia':
        return 'No Revit 2025: validar topografia/implantação, coordenadas e delimitação do terreno, atualizar vista de implantação e reexportar.'
    return 'No Revit 2025: validar item na vista correspondente, corrigir modelo/prancha e reemitir PDF de revisão.'


def explain_for_programmer(action: str, package: str, clean_problem: str, raw_text: str) -> str:
    mixed_ok = 'em conformidade' in raw_text.lower() and ('não' in raw_text.lower() or 'nao' in raw_text.lower())
    prefix = ''
    if mixed_ok:
        prefix = 'O laudo mistura trechos em conformidade com um status pendente. Isso normalmente significa que um subitem específico ainda precisa ser conferido antes de alterar o projeto. '

    if action == 'corrigir prancha':
        return prefix + 'A pendência parece estar no desenho publicado: folha, carimbo, legenda, cotas, nomes, níveis ou representação gráfica. Para você como programador, pense nisso como corrigir a tela/relatório final que será entregue, não necessariamente o banco de dados inteiro do modelo.'
    if action == 'apresentar documento':
        return prefix + 'A pendência indica ausência ou inconsistência de documento. Pode ser prancha, memorial, ART/RRT, assinatura, índice, IFC ou arquivo complementar. A ação é localizar o arquivo faltante ou gerar uma revisão correta para anexar ao pacote.'
    if action == 'compatibilizar modelo':
        return prefix + 'A pendência indica conflito entre informações. Exemplo: uma planta diz uma coisa, o corte ou a implantação mostra outra. A tarefa é fazer as informações baterem entre modelo, vistas e pranchas.'
    if action == 'revisar norma':
        return prefix + 'A pendência pede conferência contra uma regra técnica. A arquiteta precisa verificar se o desenho atende norma, medida mínima, acessibilidade ou requisito formal antes de emitir.'
    if action == 'pedir decisão':
        return prefix + 'A pendência depende de decisão externa. Antes de mexer no Revit, é preciso documentar a dúvida, mostrar a evidência e pedir validação da coordenação/gestão.'
    if action == 'revisar orçamento':
        return prefix + 'A pendência afeta quantitativo ou planilha. A correção no desenho/modelo precisa refletir nos números do orçamento ou no pacote executivo.'
    return prefix + 'O texto extraído não deixa uma ação única confiável. A primeira tarefa é abrir o laudo/PDF, entender o subitem e classificar a correção antes de executar no Revit.'


def architecture_context(package: str, clean_problem: str) -> str:
    context_by_package = {
        'cobertura/quadra': 'Esse pacote envolve quadra, cobertura, vestiários e elementos associados. Erros aqui afetam leitura de implantação, execução de cobertura, drenagem, acessos e documentação da área esportiva.',
        'acessibilidade': 'Esse pacote envolve atendimento à NBR 9050: rampas, corrimãos, guarda-corpo, piso tátil, circulação e cotas. Pequenos erros podem impedir aprovação técnica.',
        'implantação/topografia': 'Esse pacote mostra como a escola se posiciona no terreno: limites, níveis, taludes, acessos e relação com o entorno. É uma das bases para compatibilizar todo o projeto.',
        'documentos assinados': 'Esse pacote garante rastreabilidade legal e técnica: responsável, assinatura, revisão, memorial, prancha ou documento complementar. Sem isso, a entrega pode ser recusada mesmo com desenho correto.',
        'licenças/TRP': 'Esse pacote envolve documentos formais de recebimento, licença ou regularização. Normalmente não se resolve só desenhando; exige conferir documentação e aprovação.',
        'orçamento/executivo': 'Esse pacote conecta projeto e execução. O que está desenhado precisa bater com quantitativos, planilhas e documentos do executivo.',
        'triagem operacional': 'Esse pacote precisa de leitura humana do laudo porque o OCR ou o texto original não deixou uma categoria forte o bastante.',
    }
    return context_by_package.get(package, 'Esse item precisa ser conferido no pacote técnico correto antes da próxima emissão.')


def where_to_check_in_revit(package: str, action: str) -> str:
    if package == 'acessibilidade':
        return 'Vistas de planta de acessibilidade, detalhes de rampa/corrimão, cortes e folhas onde aparecem piso tátil, rampas e circulações.'
    if package == 'implantação/topografia':
        return 'Vista de implantação/site plan, níveis do terreno, limites, acessos, cotas gerais e folha de implantação.'
    if package == 'cobertura/quadra':
        return 'Plantas e cortes da quadra/cobertura/vestiários, folhas de cobertura e detalhes associados.'
    if package == 'documentos assinados':
        return 'Folhas emitidas, lista/índice de pranchas, carimbo, parâmetros de revisão e arquivos/documentos anexos ao pacote.'
    if package == 'licenças/TRP':
        return 'Índice de entrega, folhas/documentos formais e controle externo de documentação; pode não estar dentro do RVT.'
    if package == 'orçamento/executivo':
        return 'Vistas usadas para quantitativo, tabelas/schedules, folhas executivas e elementos que geram contagem/área/comprimento.'
    return 'Vista ou folha citada no laudo; se não houver referência clara, começar pelo índice de pranchas e buscar o item/seção.'


def acceptance_criteria(action: str, package: str) -> str:
    if action == 'apresentar documento':
        return 'Documento faltante anexado ou folha revisada emitida, com identificação da escola, revisão, data e responsável técnico quando aplicável.'
    if action == 'corrigir prancha':
        return 'PDF revisado mostra a informação corrigida na folha, sem conflito visual, texto ilegível ou indicação incompleta.'
    if action == 'compatibilizar modelo':
        return 'A mesma informação confere em planta, corte/elevação, implantação e folha final.'
    if action == 'revisar norma':
        return 'Medida, elemento ou indicação atende a norma aplicável e a evidência está visível na prancha ou memorial.'
    if action == 'pedir decisão':
        return 'Decisão registrada por coordenação/gestão e pendência desbloqueada antes da revisão final.'
    if action == 'revisar orçamento':
        return 'Quantitativo/planilha atualizado e coerente com o desenho ou modelo revisado.'
    return 'Item conferido contra o laudo, ação classificada e evidência anexada no controle.'


def classify_row(row, image_index, page_count):
    r = dict(row)
    r['status_original_norm'] = norm_status(r.get('status_original'))
    r['escola_curta'] = short_school(r.get('laudo', ''))
    r['observacao_extraida'] = normalize_spaces(r.get('observacao_extraida'))[:900]
    r['extracao_confianca'] = (r.get('extracao_confianca') or 'media').strip().lower()
    r['motivo_confianca'] = normalize_spaces(r.get('motivo_confianca') or 'extração anterior sem motivo registrado')
    r['possivel_duplicado'] = (r.get('possivel_duplicado') or 'false').strip().lower()
    r['grupo_deduplicacao'] = r.get('grupo_deduplicacao') or ''
    status_correcao = (r.get('status_correcao', '') or '').strip().lower()
    r['is_open'] = r['status_original_norm'] == 'NAO' and status_correcao in OPEN_STATUSES

    text = ' '.join([
        r.get('secao_detectada', ''),
        r.get('categoria_sugerida', ''),
        r.get('observacao_extraida', ''),
        r.get('item_detectado', ''),
        r.get('item_rotulo_detectado', ''),
    ]).lower()

    discipline = match_first(text, DISCIPLINE_RULES, 'outros')
    tipo = match_first(text, TYPE_RULES, 'triagem')
    owner = match_first(text, OWNER_RULES, 'arquitetura')
    package = match_first(text, PACKAGE_RULES, 'triagem operacional')
    action = match_first(text, ACTION_RULES, 'triagem técnica')

    score = 1
    if r.get('prioridade_sugerida') == 'P1':
        score += 2
    if tipo in {'modelagem', 'normativo', 'coordenação externa'}:
        score += 2
    if discipline in {'estrutura', 'eletrica', 'hidrossanitario'}:
        score += 1
    if any(k in text for k in ['compatibilizar', 'incompatível', 'incompativel', 'conflito']):
        score += 3
    if any(k in text for k in ['solicitar', 'gestão', 'gestao', 'secretaria', 'qual a', 'como se dará', 'como se dara', 'justificar']):
        score += 3
    if any(k in text for k in ['não apresentado', 'nao apresentado', 'não foi encaminhado', 'nao foi encaminhado']):
        score -= 1
    if r['status_original_norm'] != 'NAO':
        score = 0
    score = max(0, score)

    if any(k in text for k in ['solicitar', 'gestão', 'gestao', 'secretaria', 'qual a', 'como se dará', 'como se dara', 'justificar']):
        complexity = 'E4 bloqueado'
    elif any(k in text for k in ['compatibilizar', 'incompatível', 'incompativel', 'conflito', 'nbr 9050', 'acessibilidade']):
        complexity = 'E3 alto'
    elif score >= 6:
        complexity = 'E3 alto'
    elif score <= 2:
        complexity = 'E1 rápido'
    else:
        complexity = 'E2 médio'

    is_arq = discipline == 'arquitetura'
    status_exibicao = 'ativo_arquitetura' if is_arq else 'desativado_nao_arquitetura'

    preview_rel, modal_rel, origem_pdf, origem_page, img_conf = choose_image(
        r.get('laudo', ''),
        r.get('linha_texto', ''),
        image_index,
        page_count.get(canonical_key(r.get('laudo', '')), 1),
    )
    clean_problem = clean_laudo_text(r['observacao_extraida'])
    checklist = routine_checklist(action, package)

    r.update({
        'disciplina_detectada': discipline,
        'is_arquitetura': 'true' if is_arq else 'false',
        'status_exibicao': status_exibicao,
        'tipo_trabalho': tipo,
        'complexidade': complexity,
        'dono_sugerido': owner,
        'pacote_entrega': package,
        'acao_sugerida': action,
        'esforco_score': str(score),
        'tags_operacionais': ';'.join(match_all(text, PACKAGE_RULES, 'triagem operacional')[:4]),
        'o_que_fazer': build_action_text(action, discipline, text),
        'como_no_revit': build_revit_steps(discipline, action),
        'evidencia_esperada': 'Prancha/PDF revisado com item rastreável e observação de fechamento.',
        'imagem_preview_relpath': preview_rel,
        'imagem_modal_relpath': modal_rel,
        'imagem_origem_pdf': origem_pdf,
        'imagem_origem_pagina': str(origem_page),
        'imagem_confianca': img_conf,
        'problema_resumo': clean_problem[:280],
        'explicacao_programador': explain_for_programmer(action, package, clean_problem, r['observacao_extraida']),
        'contexto_arquitetura': architecture_context(package, clean_problem),
        'onde_ver_no_revit': where_to_check_in_revit(package, action),
        'passo_a_passo_revit': checklist,
        'criterio_aceite': acceptance_criteria(action, package),
    })

    return r


def counter_dict(rows, key):
    return dict(Counter((r.get(key) or 'vazio') for r in rows))


def build_school_summary(laudo, group):
    open_group = [r for r in group if r['is_open']]
    audit_group = [r for r in open_group if r['extracao_confianca'] == 'baixa' or r['possivel_duplicado'] == 'true']
    reliable_group = [r for r in open_group if r not in audit_group]
    active_group = [r for r in reliable_group if r['is_arquitetura'] == 'true']
    disabled_group = [r for r in reliable_group if r['is_arquitetura'] != 'true']
    return {
        'laudo': laudo,
        'nome': short_school(laudo),
        'total': len(group),
        'abertas_total': len(open_group),
        'abertas_confiaveis': len(reliable_group),
        'abertas_arquitetura': len(active_group),
        'abertas_desativadas': len(disabled_group),
        'abertas_auditoria': len(audit_group),
        'p1_arquitetura': sum(1 for r in active_group if r['prioridade_sugerida'] == 'P1'),
        'e1_arquitetura': sum(1 for r in active_group if r['complexidade'] == 'E1 rápido'),
        'e3_arquitetura': sum(1 for r in active_group if r['complexidade'] == 'E3 alto'),
        'e4_arquitetura': sum(1 for r in active_group if r['complexidade'] == 'E4 bloqueado'),
        'packages': Counter(r['pacote_entrega'] for r in active_group).most_common(5),
    }


def routine_checklist(action: str, package: str):
    base = [
        'Abrir o RVT da escola e localizar a vista/prancha relacionada ao pacote.',
        'Conferir o apontamento no laudo antes de alterar o modelo.',
        'Executar a correção no modelo ou na prancha, evitando ajuste apenas visual quando houver impacto de modelo.',
        'Validar a correção em planta, corte/elevação e folha de emissão.',
        'Exportar PDF revisado e anexar evidência ao controle de pendências.',
    ]
    if action == 'corrigir prancha':
        base[2] = 'Ajustar cotas, legendas, carimbo, notas e representação gráfica na vista ou na folha.'
    elif action == 'compatibilizar modelo':
        base[2] = 'Corrigir conflito de locação, nível, elemento ou referência entre modelo, vistas e prancha.'
    elif action == 'revisar norma':
        base[2] = 'Conferir exigência normativa, ajustar família/elemento/cota e registrar a referência técnica.'
    elif action == 'apresentar documento':
        base[0] = 'Separar documentação técnica do pacote e conferir se há RRT/ART, assinatura, memorial ou prancha faltante.'
        base[2] = 'Gerar ou anexar o documento faltante e refletir no índice/lista de pranchas quando aplicável.'
    elif action == 'pedir decisão':
        base[2] = 'Registrar a decisão pendente, preparar evidência visual e encaminhar para coordenação/gestão antes de alterar o RVT.'
    elif action == 'revisar orçamento':
        base[2] = 'Atualizar quantitativos a partir do modelo/pranchas e alinhar planilha com a revisão emitida.'

    if package == 'acessibilidade':
        base.insert(3, 'Checar rampas, corrimãos, guarda-corpo, piso tátil, circulação e cotas conforme NBR 9050.')
    elif package == 'implantação/topografia':
        base.insert(3, 'Checar implantação, limites, níveis, taludes, acessos e relação com o terreno.')
    elif package == 'cobertura/quadra':
        base.insert(3, 'Checar cobertura, quadra, vestiários, calhas/rufos e interferências de implantação.')
    elif package == 'documentos assinados':
        base.insert(3, 'Conferir identificação da escola, disciplina, responsável técnico, data e revisão.')

    return base


def build_revit_routines(active_rows):
    grouped = defaultdict(list)
    for row in active_rows:
        grouped[(row['acao_sugerida'], row['pacote_entrega'])].append(row)

    routines = []
    for (action, package), items in grouped.items():
        cx_counts = Counter(row['complexidade'] for row in items)
        dominant_complexity = sorted(
            cx_counts,
            key=lambda key: (COMPLEXITY_ORDER.get(key, 9), -cx_counts[key])
        )[0]
        schools = sorted({row['escola_curta'] for row in items})
        routines.append({
            'tipo': action,
            'pacote': package,
            'total': len(items),
            'complexidade_dominante': dominant_complexity,
            'escolas': schools,
            'checklist_revit': routine_checklist(action, package),
        })

    return sorted(
        routines,
        key=lambda r: (
            COMPLEXITY_ORDER.get(r['complexidade_dominante'], 9),
            -r['total'],
            r['tipo'],
            r['pacote'],
        )
    )


def write_csv(path, rows, fieldnames):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def build_data(rows):
    open_rows = [r for r in rows if r['is_open']]
    audit_rows = [r for r in open_rows if r['extracao_confianca'] == 'baixa' or r['possivel_duplicado'] == 'true']
    reliable_rows = [r for r in open_rows if r not in audit_rows]
    active_rows = [r for r in reliable_rows if r['is_arquitetura'] == 'true']
    disabled_rows = [r for r in reliable_rows if r['is_arquitetura'] != 'true']

    by_school = defaultdict(list)
    for r in rows:
        by_school[r['laudo']].append(r)

    schools = [build_school_summary(laudo, group) for laudo, group in sorted(by_school.items())]

    def sorted_items(items):
        return sorted(
            items,
            key=lambda r: (
                COMPLEXITY_ORDER.get(r['complexidade'], 9),
                PRIO_ORDER.get(r['prioridade_sugerida'], 9),
                r['dono_sugerido'],
                r['laudo'],
                r.get('item_detectado') or r.get('item_rotulo_detectado', ''),
            )
        )

    return {
        'generated_at': '2026-05-01',
        'summary': {
            'total': len(rows),
            'open_total': len(open_rows),
            'open_confiaveis': len(reliable_rows),
            'open_arquitetura': len(active_rows),
            'open_desativados': len(disabled_rows),
            'open_auditoria': len(audit_rows),
            'open_baixa_confianca': sum(1 for r in open_rows if r['extracao_confianca'] == 'baixa'),
            'open_duplicados': sum(1 for r in open_rows if r['possivel_duplicado'] == 'true'),
            'schools': len(schools),
            'p1_arquitetura': sum(1 for r in active_rows if r['prioridade_sugerida'] == 'P1'),
            'e1_arquitetura': sum(1 for r in active_rows if r['complexidade'] == 'E1 rápido'),
            'e2_arquitetura': sum(1 for r in active_rows if r['complexidade'] == 'E2 médio'),
            'e3_arquitetura': sum(1 for r in active_rows if r['complexidade'] == 'E3 alto'),
            'e4_arquitetura': sum(1 for r in active_rows if r['complexidade'] == 'E4 bloqueado'),
            'image_coverage_arquitetura': round((sum(1 for r in active_rows if r['imagem_confianca'] != 'sem_imagem') / max(1, len(active_rows))) * 100, 1),
        },
        'schools': schools,
        'breakdowns': {
            'disciplinas_ativos': counter_dict(active_rows, 'disciplina_detectada'),
            'disciplinas_desativados': counter_dict(disabled_rows, 'disciplina_detectada'),
            'owners_ativos': counter_dict(active_rows, 'dono_sugerido'),
            'complexidade_ativos': counter_dict(active_rows, 'complexidade'),
            'pacotes_ativos': counter_dict(active_rows, 'pacote_entrega'),
            'acoes_ativos': counter_dict(active_rows, 'acao_sugerida'),
            'confianca_auditoria': counter_dict(audit_rows, 'extracao_confianca'),
        },
        'rotinas_correcao': build_revit_routines(active_rows),
        'items_ativos': sorted_items(active_rows),
        'items_desativados': sorted_items(disabled_rows),
        'items_auditoria': sorted_items(audit_rows),
    }


def render_html(data):
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    return f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Painel Arquitetura - Revisões Operacionais</title>
  <link rel="icon" href="data:," />
  <style>
    :root{{
      --ink:#1a241e; --muted:#637165; --paper:#f7efdf; --card:#fffaf0; --line:#e6d9be;
      --red:#b6332d; --amber:#ad6b1d; --green:#1f7455; --blue:#2b5c84; --shadow:0 20px 55px rgba(41,34,20,.13);
    }}
    *{{box-sizing:border-box}}
    body{{margin:0;color:var(--ink);font-family:"Avenir Next Condensed","Bahnschrift","Trebuchet MS",sans-serif;background:radial-gradient(circle at 8% 0%,rgba(31,116,85,.18),transparent 30rem),radial-gradient(circle at 95% 10%,rgba(173,107,29,.18),transparent 32rem),linear-gradient(135deg,#f3e6ca,#fbf7ec 50%,#eaf0e4)}}
    header{{padding:30px clamp(16px,4vw,58px) 18px;display:grid;grid-template-columns:1.2fr .8fr;gap:16px;align-items:end}}
    h1{{margin:0;font-size:clamp(40px,6.6vw,86px);letter-spacing:-.06em;line-height:.86;font-weight:950}}
    .lead{{margin:14px 0 0;color:var(--muted);font-size:clamp(16px,1.9vw,22px);line-height:1.23;max-width:780px}}
    .note{{background:rgba(255,250,240,.86);border:1px solid var(--line);border-radius:24px;padding:16px;box-shadow:var(--shadow);display:grid;gap:8px}}
    .note b{{font-size:22px;color:var(--green)}}
    main{{padding:0 clamp(16px,4vw,58px) 56px}}
    .kpis{{display:grid;grid-template-columns:repeat(7,minmax(110px,1fr));gap:10px;margin:14px 0 16px}}
    .kpi{{background:rgba(255,250,240,.9);border:1px solid var(--line);border-radius:18px;padding:13px;box-shadow:0 10px 24px rgba(41,34,20,.08)}}
    .kpi span{{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:900}}
    .kpi b{{display:block;margin-top:6px;font-size:33px;line-height:1}}
    .toolbar{{position:sticky;top:0;z-index:20;background:rgba(247,239,223,.95);backdrop-filter:blur(14px);border:1px solid var(--line);border-radius:20px;padding:10px;display:grid;grid-template-columns:1fr repeat(5,minmax(120px,auto));gap:8px;box-shadow:0 16px 34px rgba(41,34,20,.12);margin-bottom:14px}}
    input,select,button{{font:inherit;border-radius:12px;border:1px solid var(--line);padding:10px 11px;background:#fffaf0;color:var(--ink)}}
    button{{cursor:pointer;font-weight:900}}
    button.active{{background:var(--ink);color:#fff}}
    .tabs{{display:flex;gap:8px;margin:0 0 12px}}
    .tab{{padding:10px 14px;border-radius:12px;border:1px solid var(--line);background:#fffaf0;font-weight:900;cursor:pointer}}
    .tab.active{{background:var(--ink);color:#fff}}
    .schools{{display:grid;grid-template-columns:repeat(5,minmax(180px,1fr));gap:10px;margin-bottom:14px}}
    .school{{background:rgba(255,250,240,.9);border:1px solid var(--line);border-radius:18px;padding:14px;box-shadow:0 10px 22px rgba(41,34,20,.08);position:relative;overflow:hidden}}
    .school:before{{content:"";position:absolute;inset:0 0 auto;height:6px;background:linear-gradient(90deg,var(--red),var(--amber),var(--green))}}
    .school h3{{font-size:19px;line-height:1.08;margin:8px 0 10px;min-height:42px}}
    .big{{font-size:39px;font-weight:950;letter-spacing:-.04em}}
    .chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}
    .chip{{font-size:11px;background:#f0e5cf;padding:5px 8px;border-radius:999px;font-weight:900;color:#56655b}}
    .layout{{display:grid;grid-template-columns:320px 1fr;gap:14px;align-items:start}}
    .panel{{background:rgba(255,250,240,.9);border:1px solid var(--line);border-radius:18px;padding:14px;box-shadow:0 10px 22px rgba(41,34,20,.08);position:sticky;top:92px}}
    .panel h4{{margin:0 0 10px;font-size:22px}}
    .bars{{display:grid;gap:7px}}
    .bar{{display:grid;grid-template-columns:140px 1fr 40px;gap:8px;align-items:center;font-size:12px;font-weight:900;color:#526155}}
    .track{{height:10px;border-radius:99px;background:#eadcc2;overflow:hidden}}
    .fill{{height:100%;background:var(--green)}}
    .tasks h4{{margin:2px 0 10px;font-size:24px}}
    .group{{margin:16px 0 8px;padding:8px 10px;background:#e9dcc4;border-radius:12px;font-size:17px;font-weight:950;color:#414c43}}
    .task{{display:grid;grid-template-columns:190px 200px 1fr 220px;gap:10px;background:rgba(255,250,240,.92);border:1px solid var(--line);border-left:9px solid var(--amber);border-radius:16px;padding:10px;margin-bottom:10px;box-shadow:0 8px 18px rgba(41,34,20,.07)}}
    .task[data-cx="E4 bloqueado"]{{border-left-color:var(--red)}}
    .task[data-cx="E3 alto"]{{border-left-color:var(--amber)}}
    .task[data-cx="E1 rápido"]{{border-left-color:var(--green)}}
    .task img{{width:100%;height:118px;object-fit:cover;border-radius:10px;border:1px solid var(--line);background:#f2ead9}}
    .meta{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:900}}
    .title{{font-size:13px;font-weight:900;margin:4px 0 6px}}
    .desc{{font-size:14px;line-height:1.22}}
    .block{{margin-bottom:7px}}
    .empty{{padding:24px;border-radius:16px;border:1px dashed var(--line);background:#fffaf0;color:var(--muted)}}
    .routines{{margin:0 0 16px}}
    .routines-head{{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:0 0 10px}}
    .routines-head h2{{font-size:24px;margin:0}}
    .routines-grid{{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:10px}}
    .routine{{text-align:left;background:rgba(255,250,240,.94);border:1px solid var(--line);border-left:7px solid var(--blue);border-radius:16px;padding:12px;box-shadow:0 8px 18px rgba(41,34,20,.07)}}
    .routine.active{{outline:3px solid rgba(31,116,85,.25);background:#fffaf0}}
    .routine[data-cx="E4 bloqueado"]{{border-left-color:var(--red)}}
    .routine[data-cx="E3 alto"]{{border-left-color:var(--amber)}}
    .routine[data-cx="E1 rápido"]{{border-left-color:var(--green)}}
    .routine-top{{display:flex;justify-content:space-between;gap:8px;align-items:start}}
    .routine-title{{font-size:17px;font-weight:950;line-height:1.05;margin-bottom:6px}}
    .routine-count{{font-size:31px;font-weight:950;line-height:1;color:var(--green)}}
    .routine ol{{margin:8px 0 0;padding-left:18px;font-size:13px;line-height:1.22;color:#39443c}}
    .routine-schools{{margin-top:8px;font-size:12px;color:var(--muted);font-weight:800;line-height:1.2}}
    .thumb-button{{display:block;width:100%;padding:0;border:0;background:transparent;border-radius:10px;cursor:zoom-in}}
    .thumb-button:focus-visible{{outline:3px solid var(--green);outline-offset:3px}}
    .image-modal{{position:fixed;inset:0;z-index:100;display:none;align-items:center;justify-content:center;padding:22px;background:rgba(16,22,18,.88)}}
    .image-modal.open{{display:flex}}
    .modal-card{{width:min(1500px,98vw);max-height:96vh;display:grid;grid-template-rows:auto 1fr;background:#fffaf0;border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.35)}}
    .modal-head{{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;border-bottom:1px solid var(--line)}}
    .modal-title{{font-size:18px;font-weight:950;line-height:1.1}}
    .modal-close{{width:42px;height:42px;border-radius:50%;font-size:24px;line-height:1;background:var(--ink);color:#fff;border:0}}
    .modal-body{{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:0;min-height:0}}
    .modal-image-wrap{{overflow:auto;background:#191f1b;display:flex;align-items:flex-start;justify-content:center}}
    .modal-body img{{width:100%;min-width:1120px;height:auto;background:#191f1b}}
    .modal-info{{padding:14px;border-left:1px solid var(--line);overflow:auto}}
    .modal-info .block{{font-size:14px;line-height:1.25}}
    .modal-info ol{{margin:6px 0 12px;padding-left:18px;font-size:14px;line-height:1.28}}
    @media(max-width:1220px){{header,.layout{{grid-template-columns:1fr}}.kpis{{grid-template-columns:repeat(3,1fr)}}.schools{{grid-template-columns:repeat(2,1fr)}}.toolbar{{grid-template-columns:1fr 1fr}}.toolbar input{{grid-column:1/-1}}.panel{{position:relative;top:0}}.task{{grid-template-columns:1fr}}.routines-grid{{grid-template-columns:1fr 1fr}}}}
    @media(max-width:760px){{.routines-grid,.modal-body{{grid-template-columns:1fr}}.modal-info{{border-left:0;border-top:1px solid var(--line)}}.modal-card{{max-height:96vh}}.modal-body img{{min-width:980px}}}}
    @media print{{.toolbar,.tabs,.routines,.image-modal{{display:none}}body{{background:#fff}}.kpi,.school,.panel,.task{{box-shadow:none}}}}
  </style>
</head>
<body>
<header>
  <section>
    <h1>Painel Arquitetura</h1>
    <p class="lead">Itens de arquitetura ativos por padrão. Engenharia, topografia e elétrica ficam na aba desativados com rastreabilidade.</p>
  </section>
  <aside class="note">
    <b>Regra operacional</b>
    <span>Fechar primeiro E4 e E3. Usar E1 como quick wins. Sempre anexar evidência de revisão.</span>
    <span class="meta">Recortes de imagem: associação semiautomática por laudo + página estimada</span>
  </aside>
</header>
<main>
  <section class="kpis" id="kpis"></section>
  <section class="toolbar">
    <input id="search" placeholder="Buscar por problema, ação, Revit, escola..." />
    <select id="school"></select>
    <select id="owner"></select>
    <select id="package"></select>
    <select id="complexity"></select>
    <button id="quick">Quick wins</button>
  </section>

  <section class="tabs">
    <button class="tab active" data-tab="ativos">Arquitetura Ativos</button>
    <button class="tab" data-tab="desativados">Desativados (Nao Arquitetura)</button>
    <button class="tab" data-tab="auditoria">Auditoria da Extração</button>
  </section>

  <section class="schools" id="schools"></section>

  <section class="routines">
    <div class="routines-head">
      <h2>Rotinas de Correção no Revit</h2>
      <button id="clearRoutine">Limpar rotina</button>
    </div>
    <div id="routines" class="routines-grid"></div>
  </section>

  <section class="layout">
    <aside class="panel">
      <h4>Distribuição</h4>
      <div class="meta">Dono sugerido (visão atual)</div>
      <div id="owners" class="bars"></div>
      <div class="meta" style="margin-top:10px">Pacote de entrega</div>
      <div id="packages" class="bars"></div>
    </aside>

    <section class="tasks">
      <h4 id="taskTitle">Itens</h4>
      <div id="tasks"></div>
    </section>
  </section>
</main>
<div id="imageModal" class="image-modal" aria-hidden="true">
  <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
    <div class="modal-head">
      <div>
        <div id="modalTitle" class="modal-title"></div>
        <div id="modalMeta" class="meta"></div>
      </div>
      <button id="modalClose" class="modal-close" aria-label="Fechar imagem">×</button>
    </div>
    <div class="modal-body">
      <div class="modal-image-wrap">
        <img id="modalImage" alt="Recorte ampliado do laudo" />
      </div>
      <div id="modalInfo" class="modal-info"></div>
    </div>
  </div>
</div>
<script id="payload" type="application/json">{payload}</script>
<script>
const data = JSON.parse(document.getElementById('payload').textContent);
let state = {{tab:'ativos', school:'all', owner:'all', package:'all', complexity:'all', q:'', quick:false, routine:null}};
let renderedItems = [];
const $ = (id)=>document.getElementById(id);
const entries = (o)=>Object.entries(o||{{}}).sort((a,b)=>b[1]-a[1]);

function escapeHtml(value){{
  return String(value ?? '').replace(/[&<>"']/g, ch => ({{
    '&':'&amp;',
    '<':'&lt;',
    '>':'&gt;',
    '"':'&quot;',
    "'":'&#39;'
  }}[ch]));
}}

function safeImagePath(value){{
  const path = String(value || '');
  return (path.startsWith('assets/previews/') || path.startsWith('assets/previews-full/')) ? path : 'assets/previews/sem_imagem.svg';
}}

function routineKey(routine){{
  return routine.tipo + '||' + routine.pacote;
}}

function optionFill(id, label, vals){{
  $(id).innerHTML = `<option value="all">${{escapeHtml(label)}}</option>` + vals.map(v=>`<option value="${{escapeHtml(v)}}">${{escapeHtml(v)}}</option>`).join('');
}}

function renderKpis(){{
  const s = data.summary;
  $('kpis').innerHTML = [
    ['Escolas', s.schools],
    ['Abertas total', s.open_total],
    ['Confiáveis', s.open_confiaveis],
    ['Arquitetura', s.open_arquitetura],
    ['Auditoria', s.open_auditoria],
    ['Duplicados', s.open_duplicados],
    ['P1 arquitetura', s.p1_arquitetura],
    ['Cobertura imagem %', s.image_coverage_arquitetura + '%']
  ].map(x=>`<article class="kpi"><span>${{escapeHtml(x[0])}}</span><b>${{escapeHtml(x[1])}}</b></article>`).join('');
}}

function renderSchools(){{
  $('schools').innerHTML = data.schools.map(s=>`<article class="school"><h3>${{escapeHtml(s.nome)}}</h3><div class="meta">abertas arquitetura confiáveis</div><div class="big">${{escapeHtml(s.abertas_arquitetura)}}</div><div class="chips"><span class="chip">P1 ${{escapeHtml(s.p1_arquitetura)}}</span><span class="chip">E1 ${{escapeHtml(s.e1_arquitetura)}}</span><span class="chip">E3 ${{escapeHtml(s.e3_arquitetura)}}</span><span class="chip">E4 ${{escapeHtml(s.e4_arquitetura)}}</span><span class="chip">Auditoria ${{escapeHtml(s.abertas_auditoria)}}</span></div></article>`).join('');
}}

function bars(id, obj){{
  const e = entries(obj);
  const max = Math.max(1, ...e.map(x=>x[1]));
  $(id).innerHTML = e.map(([k,v])=>`<div class="bar"><span>${{escapeHtml(k)}}</span><div class="track"><div class="fill" style="width:${{Math.round(v/max*100)}}%"></div></div><span>${{escapeHtml(v)}}</span></div>`).join('');
}}

function currentItems(){{
  if (state.tab === 'ativos') return data.items_ativos;
  if (state.tab === 'auditoria') return data.items_auditoria || [];
  return data.items_desativados;
}}

function filteredItems(){{
  const q = state.q.toLowerCase();
  return currentItems()
    .filter(r=>state.school==='all' || r.laudo===state.school)
    .filter(r=>state.owner==='all' || r.dono_sugerido===state.owner)
    .filter(r=>state.package==='all' || r.pacote_entrega===state.package)
    .filter(r=>state.complexity==='all' || r.complexidade===state.complexity)
    .filter(r=>!state.quick || r.complexidade==='E1 rápido')
    .filter(r=>!state.routine || (r.acao_sugerida === state.routine.tipo && r.pacote_entrega === state.routine.pacote))
    .filter(r=>!q || JSON.stringify(r).toLowerCase().includes(q));
}}

function renderRoutines(){{
  if (state.tab !== 'ativos') {{
    $('routines').innerHTML = '<div class="empty">Rotinas Revit aparecem apenas para itens ativos de arquitetura confiáveis.</div>';
    $('clearRoutine').style.display = 'none';
    return;
  }}
  $('clearRoutine').style.display = state.routine ? 'inline-block' : 'none';
  $('routines').innerHTML = (data.rotinas_correcao || []).map(routine => {{
    const active = state.routine && routine.tipo === state.routine.tipo && routine.pacote === state.routine.pacote;
    const steps = (routine.checklist_revit || []).slice(0, 6).map(step=>`<li>${{escapeHtml(step)}}</li>`).join('');
    const schools = (routine.escolas || []).slice(0, 4).join(' • ');
    return `
      <button class="routine ${{active ? 'active' : ''}}" data-key="${{escapeHtml(routineKey(routine))}}" data-cx="${{escapeHtml(routine.complexidade_dominante)}}">
        <div class="routine-top">
          <div>
            <div class="routine-title">${{escapeHtml(routine.tipo)}}</div>
            <div class="meta">${{escapeHtml(routine.pacote)}} • ${{escapeHtml(routine.complexidade_dominante)}}</div>
          </div>
          <div class="routine-count">${{escapeHtml(routine.total)}}</div>
        </div>
        <ol>${{steps}}</ol>
        <div class="routine-schools">${{escapeHtml(schools)}}${{routine.escolas.length > 4 ? ' +' + (routine.escolas.length - 4) : ''}}</div>
      </button>
    `;
  }}).join('');
}}

function renderTasks(){{
  const items = filteredItems();
  renderedItems = items.slice(0, 220);
  const tabLabel = state.tab === 'ativos' ? 'Arquitetura Ativos' : (state.tab === 'auditoria' ? 'Auditoria da Extração' : 'Desativados');
  $('taskTitle').textContent = 'Itens (' + items.length + ') - ' + tabLabel;
  if (!items.length) {{
    $('tasks').innerHTML = '<div class="empty">Nenhum item com os filtros atuais.</div>';
    return;
  }}

  let html = '';
  let prevOwner = '';
  renderedItems.forEach((r, idx) => {{
    if (r.dono_sugerido !== prevOwner) {{
      prevOwner = r.dono_sugerido;
      html += `<div class="group">${{escapeHtml(prevOwner)}}</div>`;
    }}
    const itemLabel = r.item_detectado || r.item_rotulo_detectado || '-';
    html += `
      <article class="task" data-cx="${{escapeHtml(r.complexidade)}}">
        <div>
          <button class="thumb-button" data-image-index="${{idx}}" aria-label="Abrir recorte em tela cheia">
            <img src="${{escapeHtml(safeImagePath(r.imagem_preview_relpath))}}" alt="preview item" loading="lazy" />
          </button>
          <div class="meta">${{escapeHtml(r.imagem_origem_pdf)}}</div>
          <div class="meta">pag. ${{escapeHtml(r.imagem_origem_pagina || '-')}} • conf. ${{escapeHtml(r.imagem_confianca)}}</div>
        </div>
        <div>
          <div class="title">${{escapeHtml(r.escola_curta)}}</div>
          <div class="meta">item ${{escapeHtml(itemLabel)}} • ${{escapeHtml(r.complexidade)}} • ${{escapeHtml(r.prioridade_sugerida)}}</div>
          <div class="meta">${{escapeHtml(r.disciplina_detectada)}} • ${{escapeHtml(r.pacote_entrega)}}</div>
          <div class="meta">${{escapeHtml(r.status_exibicao)}}</div>
          <div class="meta">extração: ${{escapeHtml(r.extracao_confianca)}} ${{r.possivel_duplicado === 'true' ? '• possível duplicado' : ''}}</div>
        </div>
        <div class="desc">
          <div class="block"><b>Problema:</b> ${{escapeHtml(r.problema_resumo)}}</div>
          <div class="block"><b>Explicação:</b> ${{escapeHtml(r.explicacao_programador)}}</div>
          <div class="block"><b>Confiança:</b> ${{escapeHtml(r.motivo_confianca)}}</div>
          <div class="block"><b>Ação:</b> ${{escapeHtml(r.o_que_fazer)}}</div>
          <div class="block"><b>Como no Revit:</b> ${{escapeHtml(r.como_no_revit)}}</div>
        </div>
        <div>
          <div class="meta">dono sugerido</div>
          <div class="title">${{escapeHtml(r.dono_sugerido)}}</div>
          <div class="meta">tipo</div>
          <div class="title">${{escapeHtml(r.tipo_trabalho)}}</div>
          <div class="meta">ação sugerida</div>
          <div class="title">${{escapeHtml(r.acao_sugerida)}}</div>
          <div class="meta">modal</div>
          <div class="title">Clique na imagem para ver explicação completa</div>
        </div>
      </article>
    `;
  }});

  $('tasks').innerHTML = html;
}}

function openImageModal(row){{
  const itemLabel = row.item_detectado || row.item_rotulo_detectado || '-';
  $('modalTitle').textContent = (row.escola_curta || 'Escola') + ' • item ' + itemLabel;
  $('modalMeta').textContent = (row.imagem_origem_pdf || '-') + ' • pag. ' + (row.imagem_origem_pagina || '-') + ' • conf. ' + (row.imagem_confianca || '-');
  $('modalImage').src = safeImagePath(row.imagem_modal_relpath || row.imagem_preview_relpath);
  const steps = Array.isArray(row.passo_a_passo_revit) ? row.passo_a_passo_revit : [];
  $('modalInfo').innerHTML = `
    <div class="block"><b>Problema no laudo:</b> ${{escapeHtml(row.problema_resumo)}}</div>
    <div class="block"><b>Confiança da extração:</b> ${{escapeHtml(row.extracao_confianca)}} - ${{escapeHtml(row.motivo_confianca)}}${{row.possivel_duplicado === 'true' ? ' - possível duplicado' : ''}}</div>
    <div class="block"><b>Explicação para programador:</b> ${{escapeHtml(row.explicacao_programador)}}</div>
    <div class="block"><b>Contexto:</b> ${{escapeHtml(row.contexto_arquitetura)}}</div>
    <div class="block"><b>Onde conferir no Revit:</b> ${{escapeHtml(row.onde_ver_no_revit)}}</div>
    <div class="block"><b>Como conferir no Revit:</b></div>
    <ol>${{steps.map(step => `<li>${{escapeHtml(step)}}</li>`).join('')}}</ol>
    <div class="block"><b>Critério de aceite:</b> ${{escapeHtml(row.criterio_aceite)}}</div>
    <div class="block"><b>Pacote:</b> ${{escapeHtml(row.pacote_entrega)}} / ${{escapeHtml(row.complexidade)}}</div>
  `;
  $('imageModal').classList.add('open');
  $('imageModal').setAttribute('aria-hidden', 'false');
  $('modalClose').focus();
}}

function closeImageModal(){{
  $('imageModal').classList.remove('open');
  $('imageModal').setAttribute('aria-hidden', 'true');
  $('modalImage').removeAttribute('src');
}}

function rebindFilters(){{
  const base = currentItems();
  optionFill('school', 'Todas as escolas', [...new Set(base.map(x=>x.laudo))]);
  optionFill('owner', 'Todos os donos', [...new Set(base.map(x=>x.dono_sugerido))]);
  optionFill('package', 'Todos os pacotes', [...new Set(base.map(x=>x.pacote_entrega))]);
  optionFill('complexity', 'Todas complexidades', [...new Set(base.map(x=>x.complexidade))]);

  state.school = 'all';
  state.owner = 'all';
  state.package = 'all';
  state.complexity = 'all';
  state.q = '';
  state.routine = null;
  $('search').value = '';
  state.quick = false;
  $('quick').classList.remove('active');
}}

function renderBreakdowns(){{
  if (state.tab === 'ativos') {{
    bars('owners', data.breakdowns.owners_ativos);
    bars('packages', data.breakdowns.pacotes_ativos);
  }} else if (state.tab === 'auditoria') {{
    bars('owners', data.breakdowns.confianca_auditoria);
    bars('packages', data.breakdowns.disciplinas_desativados);
  }} else {{
    bars('owners', data.breakdowns.disciplinas_desativados);
    bars('packages', data.breakdowns.disciplinas_desativados);
  }}
}}

function wire(){{
  $('search').oninput = e => {{ state.q = e.target.value; renderTasks(); }};
  $('school').onchange = e => {{ state.school = e.target.value; renderTasks(); }};
  $('owner').onchange = e => {{ state.owner = e.target.value; renderTasks(); }};
  $('package').onchange = e => {{ state.package = e.target.value; renderTasks(); }};
  $('complexity').onchange = e => {{ state.complexity = e.target.value; renderTasks(); }};
  $('quick').onclick = () => {{ state.quick = !state.quick; $('quick').classList.toggle('active', state.quick); renderTasks(); }};
  $('clearRoutine').onclick = () => {{ state.routine = null; renderRoutines(); renderTasks(); }};

  $('routines').onclick = e => {{
    const btn = e.target.closest('.routine');
    if (!btn) return;
    const [tipo, pacote] = btn.dataset.key.split('||');
    state.routine = {{tipo, pacote}};
    renderRoutines();
    renderTasks();
    document.querySelector('.tasks').scrollIntoView({{behavior:'smooth', block:'start'}});
  }};

  $('tasks').onclick = e => {{
    const btn = e.target.closest('.thumb-button');
    if (!btn) return;
    const row = renderedItems[Number(btn.dataset.imageIndex)];
    if (row) openImageModal(row);
  }};

  $('modalClose').onclick = closeImageModal;
  $('imageModal').onclick = e => {{ if (e.target.id === 'imageModal') closeImageModal(); }};
  document.addEventListener('keydown', e => {{
    if (e.key === 'Escape' && $('imageModal').classList.contains('open')) closeImageModal();
  }});

  document.querySelectorAll('.tab').forEach(btn => {{
    btn.onclick = () => {{
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      state.tab = btn.dataset.tab;
      rebindFilters();
      renderBreakdowns();
      renderRoutines();
      renderTasks();
    }};
  }});
}}

renderKpis();
renderSchools();
rebindFilters();
renderBreakdowns();
renderRoutines();
wire();
renderTasks();
</script>
</body>
</html>'''


def main():
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    FULL_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    image_index, page_count = build_image_index()

    with SOURCE_CSV.open(encoding='utf-8') as handle:
        base_rows = list(csv.DictReader(handle))

    rows = [classify_row(r, image_index, page_count) for r in base_rows]
    fieldnames = list(rows[0].keys()) if rows else []

    write_csv(CLASSIFIED_CSV, rows, fieldnames)
    data = build_data(rows)

    DATA_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    html = render_html(data)
    INDEX_HTML.write_text(html, encoding='utf-8')
    LEGACY_HTML.write_text(html, encoding='utf-8')

    print(INDEX_HTML)
    print(DATA_JSON)
    print(CLASSIFIED_CSV)
    print('preview_count', len(list(PREVIEW_DIR.glob('*'))))
    print(json.dumps(data['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
