#!/usr/bin/env python3
from pathlib import Path
import csv
import hashlib
import re
import unicodedata
from collections import Counter, defaultdict

BASE = Path('/Users/leandrobosaipo/Projetos/Arq')
TEXT_DIR = BASE / '_trabalho' / 'textos'
OUT_DIR = BASE / '_trabalho' / 'entregaveis'
OUT_DIR.mkdir(parents=True, exist_ok=True)

STATUS_RE = re.compile(r'\b(NÃO|NAO|SIM|N/A|Anexo\s+\d+)\b', re.I)
TARGET_STATUS_RE = re.compile(r'\b(NÃO|NAO|N/A)\b', re.I)
ITEM_RE = re.compile(r'^\s*(\d{1,2}(?:\.\d{1,2})?)\s+(.+?)\s*$')
LABEL_STATUS_RE = re.compile(r'^\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç0-9°ªº\-/(),. ]{5,}?)\s+(BÁSICO|BASICO|EXECUTIVO\s+)?(NÃO|NAO|N/A)\b', re.I)
SECTION_RE = re.compile(r'^\s*(\d{1,2})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ\s\-/]+?)\s+(MATERIAL|DOCUMENTO|FASE|CONFORME|OBSERVAÇÕES)\b')
PAGE_RE = re.compile(r'Página\s+\d+\s+de\s+\d+', re.I)
SEDUC_RE = re.compile(r'\bSEDUC[A-Z0-9]+\b', re.I)
LEGEND_RE = re.compile(r'SIM\s*-\s*REFERE-SE|CONFORMIDADE DO ITEM|ITEM COM PENDÊNCIA', re.I)

KEYWORDS = {
    'documento_ausente': ['não apresentado', 'nao apresentado', 'item não apresentado', 'item nao apresentado', 'não foi encaminhado'],
    'compatibilizacao': ['compatibilizar', 'incompatível', 'incompativel', 'coerência', 'coerencia', 'conflito'],
    'grafico_prancha': ['legenda', 'carimbo', 'representação gráfica', 'representacao grafica', 'prancha', 'sobreposição', 'sobreposicao', 'ilegível', 'ilegivel'],
    'cotas_niveis': ['cota', 'nível', 'nivel', 'desnível', 'desnivel', 'inclinação', 'inclinacao', 'rampa'],
    'acessibilidade': ['acessibilidade', 'piso tátil', 'piso tatil', 'nbr 9050', 'corrimão', 'corrimao', 'guarda-corpo'],
    'implantacao': ['implantação', 'implantacao', 'terreno', 'perímetro', 'perimetro', 'área do terreno', 'area do terreno', 'locação', 'locacao'],
    'cobertura_quadra': ['cobertura', 'quadra', 'telhado', 'rufo', 'calha'],
    'instalacoes': ['elétrica', 'eletrica', 'hidráulica', 'hidraulica', 'spda', 'incêndio', 'incendio', 'climatização', 'climatizacao', 'lógica', 'logica', 'gás', 'gas'],
    'orcamento': ['orçamentária', 'orcamentaria', 'planilha', 'composição', 'composicao', 'cotações', 'cotacoes'],
}

FIELDNAMES = [
    'laudo', 'linha_texto', 'linha_inicio', 'linha_fim', 'secao_detectada', 'item_detectado',
    'item_rotulo_detectado',
    'status_original', 'categoria_sugerida', 'prioridade_sugerida', 'observacao_extraida',
    'texto_limpo', 'texto_original_bloco', 'extracao_confianca', 'motivo_confianca',
    'possivel_duplicado', 'grupo_deduplicacao', 'responsavel', 'status_correcao',
    'evidencia_correcao', 'data_limite',
]


def normalize_spaces(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '').strip())


def canonical(value: str) -> str:
    text = unicodedata.normalize('NFKD', value or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return normalize_spaces(text)


def is_noise_line(line: str) -> bool:
    text = normalize_spaces(line)
    if not text:
        return True
    return bool(PAGE_RE.search(text) or SEDUC_RE.search(text))


def clean_text(value: str) -> str:
    text = normalize_spaces(value)
    text = PAGE_RE.sub('', text)
    text = SEDUC_RE.sub('', text)
    text = re.sub(r'\bPROJ\.\s*', '', text, flags=re.I)
    text = re.sub(r'\b(BÁSICO|BASICO|EXECUTIVO)\b', '', text, flags=re.I)
    text = re.sub(r'\b(DESENHO|DOCUMENTO|MEMORIAL|RELATÓRIO|RELATORIO|TABELA)\b', '', text, flags=re.I)
    text = re.sub(r'\b(NÃO|NAO|N/A)\b', '', text, flags=re.I)
    text = re.sub(r'\s+([.,;:])', r'\1', text)
    return normalize_spaces(text)


def classify_categories(text: str):
    low = text.lower()
    cats = [name for name, terms in KEYWORDS.items() if any(term in low for term in terms)]
    return cats or ['triagem_manual']


def detect_status(text: str) -> str:
    matches = [m.group(1).upper().replace('NAO', 'NÃO') for m in STATUS_RE.finditer(text)]
    if 'NÃO' in matches:
        return 'NÃO'
    if 'N/A' in matches:
        return 'N/A'
    if 'SIM' in matches:
        return 'SIM'
    return ''


def confidence_for(item: str, label: str, raw_block: str, cleaned: str, status: str):
    reasons = []
    confidence = 'alta'
    if not item:
        if label:
            confidence = 'media'
            reasons.append('linha de tabela sem numeracao mas com rotulo e status')
        else:
            confidence = 'baixa'
            reasons.append('sem item numerado')
    if LEGEND_RE.search(raw_block):
        confidence = 'baixa'
        reasons.append('texto parece legenda de conformidade')
    if PAGE_RE.search(raw_block) or SEDUC_RE.search(raw_block):
        reasons.append('rodape/cabecalho removido')
    if re.search(r'\b\d{1,2}\.\d{1,2}\b.*\b\d{1,2}\.\d{1,2}\b', cleaned):
        confidence = 'media' if confidence == 'alta' else confidence
        reasons.append('bloco pode conter mais de um subitem')
    if re.search(r'em conformidade', raw_block, re.I) and status == 'NÃO':
        confidence = 'media' if confidence == 'alta' else confidence
        reasons.append('mistura conformidade com status pendente')
    if len(cleaned) < 18:
        confidence = 'media' if confidence == 'alta' else confidence
        reasons.append('observacao curta exige conferencia')
    if not reasons:
        reasons.append('item numerado com status e observacao coerente')
    return confidence, '; '.join(reasons)


def priority_for(status: str, cats, confidence: str) -> str:
    if status != 'NÃO':
        return 'P3'
    if confidence == 'baixa':
        return 'P3'
    if {'documento_ausente', 'compatibilizacao', 'acessibilidade'} & set(cats):
        return 'P1'
    return 'P2'


def make_group_key(laudo: str, item: str, label: str, section: str, cleaned: str) -> str:
    seed = '|'.join([canonical(laudo), canonical(item or label), canonical(section), canonical(cleaned)[:220]])
    return hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]


def emit_row(txt_stem: str, current_section: str, block):
    raw_lines = [line for _, line in block]
    raw_block = normalize_spaces(' '.join(raw_lines))
    if not TARGET_STATUS_RE.search(raw_block):
        return None

    first_line_no = block[0][0]
    last_line_no = block[-1][0]
    first_line = normalize_spaces(raw_lines[0])
    item_match = ITEM_RE.match(first_line)
    label_match = LABEL_STATUS_RE.match(first_line)
    item = item_match.group(1) if item_match else ''
    label = clean_text(label_match.group(1)) if label_match and not item else ''
    status = detect_status(raw_block)
    cleaned = clean_text(raw_block)
    cats = classify_categories(cleaned)
    confidence, reason = confidence_for(item, label, raw_block, cleaned, status)
    group = make_group_key(txt_stem, item, label, current_section, cleaned)

    return {
        'laudo': txt_stem,
        'linha_texto': str(first_line_no),
        'linha_inicio': str(first_line_no),
        'linha_fim': str(last_line_no),
        'secao_detectada': current_section,
        'item_detectado': item,
        'item_rotulo_detectado': label,
        'status_original': status,
        'categoria_sugerida': ';'.join(cats),
        'prioridade_sugerida': priority_for(status, cats, confidence),
        'observacao_extraida': cleaned[:900],
        'texto_limpo': cleaned[:1400],
        'texto_original_bloco': raw_block[:1800],
        'extracao_confianca': confidence,
        'motivo_confianca': reason,
        'possivel_duplicado': 'false',
        'grupo_deduplicacao': group,
        'responsavel': '',
        'status_correcao': 'aberto' if status == 'NÃO' else 'futuro_executivo_ou_nao_aplica',
        'evidencia_correcao': '',
        'data_limite': '',
    }


def extract_file(txt: Path):
    lines = txt.read_text(errors='replace').splitlines()
    current_section = ''
    rows = []
    summary = Counter()
    block = []
    block_section = ''

    def flush():
        nonlocal block, block_section
        if block:
            row = emit_row(txt.stem, block_section, block)
            if row:
                rows.append(row)
                summary[row['status_original']] += 1
        block = []
        block_section = current_section

    for idx, line in enumerate(lines, start=1):
        if is_noise_line(line):
            continue

        sec = SECTION_RE.search(line)
        if sec:
            flush()
            current_section = normalize_spaces(sec.group(2))
            block_section = current_section
            continue

        normalized = normalize_spaces(line)
        item_match = ITEM_RE.match(normalized)
        label_match = LABEL_STATUS_RE.match(normalized)
        has_target_status = bool(TARGET_STATUS_RE.search(normalized))

        if item_match:
            flush()
            block = [(idx, normalized)]
            block_section = current_section
            continue

        if label_match and not LEGEND_RE.search(normalized):
            flush()
            block = [(idx, normalized)]
            block_section = current_section
            flush()
            continue

        if block:
            # Continuation lines belong to the current item until the next item/section.
            block.append((idx, normalized))
            continue

    flush()
    return rows, summary


rows = []
summary = defaultdict(Counter)
for txt in sorted(TEXT_DIR.glob('*.txt')):
    file_rows, file_summary = extract_file(txt)
    rows.extend(file_rows)
    summary[txt.stem].update(file_summary)

dups = Counter(r['grupo_deduplicacao'] for r in rows)
for row in rows:
    row['possivel_duplicado'] = 'true' if dups[row['grupo_deduplicacao']] > 1 else 'false'
    if row['possivel_duplicado'] == 'true' and row['extracao_confianca'] == 'alta':
        row['extracao_confianca'] = 'media'
        row['motivo_confianca'] += '; possivel duplicado'

with (OUT_DIR / 'matriz_pendencias_extraidas.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)

with (OUT_DIR / 'resumo_quantitativo_laudos.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['laudo', 'nao', 'sim', 'na', 'anexo_01', 'anexo_02', 'linhas_pendencias_extraidas', 'baixa_confianca', 'duplicados'])
    by_laudo_rows = Counter(r['laudo'] for r in rows)
    low_by_laudo = Counter(r['laudo'] for r in rows if r['extracao_confianca'] == 'baixa')
    dup_by_laudo = Counter(r['laudo'] for r in rows if r['possivel_duplicado'] == 'true')
    for laudo in sorted(summary):
        c = summary[laudo]
        writer.writerow([laudo, c['NÃO'], c['SIM'], c['N/A'], c['Anexo 01'], c['Anexo 02'], by_laudo_rows[laudo], low_by_laudo[laudo], dup_by_laudo[laudo]])

cat_counter = Counter()
prio_counter = Counter()
confidence_counter = Counter(r['extracao_confianca'] for r in rows)
for r in rows:
    prio_counter[r['prioridade_sugerida']] += 1
    for c in r['categoria_sugerida'].split(';'):
        cat_counter[c] += 1

with (OUT_DIR / 'resumo_categorias.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['categoria', 'ocorrencias'])
    for cat, count in cat_counter.most_common():
        writer.writerow([cat, count])
    writer.writerow([])
    writer.writerow(['prioridade', 'ocorrencias'])
    for prio, count in sorted(prio_counter.items()):
        writer.writerow([prio, count])
    writer.writerow([])
    writer.writerow(['extracao_confianca', 'ocorrencias'])
    for conf, count in sorted(confidence_counter.items()):
        writer.writerow([conf, count])

print(f'rows={len(rows)}')
print(f"baixa_confianca={confidence_counter['baixa']}")
print(f"duplicados={sum(1 for r in rows if r['possivel_duplicado'] == 'true')}")
print(OUT_DIR / 'matriz_pendencias_extraidas.csv')
