"""Импорт истории болезни из текста или PDF: извлечение ключевых сведений по правилам.

Разбор не зависит от порядка разделов и шаблона: заголовки ищутся по словарю синонимов
(«Жалобы», «Ds:», «An. morbi», «АНАМНЕЗ ЗАБОЛЕВАНИЯ» и т. п.), признаки риска — по всему тексту
с учётом отрицаний («суицидальные мысли отрицает»). Результат — черновик для врача:
в клиническую сводку он попадает только после подтверждения.
"""

import io
import re
from datetime import date
from typing import Any

MAX_BYTES = 5 * 1024 * 1024

SECTIONS: dict[str, tuple[str, ...]] = {
    'visit_reason': ('причина обращения', 'повод обращения', 'цель обращения', 'цель визита', 'причина госпитализации', 'направлен с целью'),
    'complaints': ('жалобы со слов пациентки', 'жалобы со слов пациента', 'жалобы со слов', 'жалобы при поступлении', 'жалобы на момент осмотра', 'жалобы пациента', 'жалобы', 'subjective', 'complaints', 's'),
    'history': ('анамнез заболевания', 'anamnesis morbi', 'an. morbi', 'an.morbi', 'история настоящего заболевания', 'развитие заболевания', 'анамнез болезни'),
    'life_history': ('анамнез жизни', 'anamnesis vitae', 'an. vitae', 'an.vitae', 'семейный и социальный анамнез'),
    'comorbidities': ('сопутствующие заболевания', 'сопутствующая патология', 'перенесённые заболевания', 'перенесенные заболевания', 'хронические заболевания', 'соматический статус', 'сопутствующий диагноз', 'сопутствующие'),
    'current_medications': ('принимаемые препараты', 'текущая терапия', 'текущее лечение', 'лекарственный анамнез', 'получаемая терапия', 'принимает', 'медикаменты', 'препараты', 'терапия на момент осмотра'),
    'allergies': ('аллергологический анамнез', 'аллергоанамнез', 'аллергии', 'аллергия', 'непереносимость лекарств', 'лекарственная непереносимость'),
    'diagnosis': ('клинический диагноз', 'основной диагноз', 'предварительный диагноз', 'диагноз основной', 'диагноз', 'ds', 'assessment', 'a'),
    'mental_status': ('психический статус', 'status mentalis', 'психический статус при осмотре', 'объективно', 'objective', 'o'),
    'scales': ('психометрия', 'шкалы', 'психометрические шкалы', 'результаты шкал'),
    'plan': ('рекомендации', 'план', 'план лечения', 'plan', 'p'),
}

SHORT_SECTIONS = {'visit_reason', 'allergies', 'diagnosis', 'current_medications', 'scales'}
HEADER_ALIASES = sorted(((alias, key) for key, aliases in SECTIONS.items() for alias in aliases), key=lambda item: -len(item[0]))
HEADER_RE = re.compile(
    r'^\s*(?:\d{1,2}[.)]\s*)?(?:#+\s*)?(?P<name>' + '|'.join(re.escape(alias) for alias, _ in HEADER_ALIASES) + r')\s*(?P<sep>[:.\-—|]|$)\s*(?P<rest>.*)$',
    re.IGNORECASE,
)
INLINE_HEADER_RE = re.compile(
    r'(?<=[.!?])\s+(?=(?:' + '|'.join(re.escape(alias) for alias, _ in HEADER_ALIASES if len(alias) > 2) + r')\s*:)',
    re.IGNORECASE,
)
UNCERTAIN = r'не\s+исключ\w*|под вопросом|\?'

NEGATION = re.compile(r'\b(отрицает|отрицаются|отрицают|нет|не\s+[а-я]+(?:ет|ит|ят|ут|ют|ется|ится)\b|не\s+(?:выявлен\w*|обнаружен\w*|высказывает|отмечает|отмечается|наблюдается|было|имеет|беременна|кормит|употребляет|выявляется)|без|отсутству\w*|исключен\w*|не\s+отягощ\w*)\b', re.IGNORECASE)

SELF_HARM = re.compile(r'суицид\w*|мысл\w* о смерти|самоповрежд\w*|нежелани\w* жить|не хочет жить|самоубийств\w*|аутоагресс\w*', re.IGNORECASE)
PSYCHOSIS = re.compile(r'галлюцинац\w*|бред\w*|голос[аов]* в голове|слышит голоса|психотическ\w*|императивн\w*', re.IGNORECASE)

FACTOR_PATTERNS: dict[str, re.Pattern[str]] = {
    'breastfeeding': re.compile(r'грудн\w* вскармливан\w*|кормит грудью|период лактации', re.IGNORECASE),
    'epilepsy_or_brain_disease': re.compile(r'эпилепс\w*|судорожн\w* (?:синдром|припад)\w*|органическ\w* (?:поражени|заболевани|расстройств)\w*|онмк|инсульт\w*|черепно-мозгов\w* травм\w*|опухол\w* головного мозга|энцефалопат\w*', re.IGNORECASE),
    'hepatic_impairment': re.compile(r'печ[её]ночн\w* недостаточн\w*|цирроз\w*|чайлд', re.IGNORECASE),
    'lactose_disorder': re.compile(r'лактазн\w* недостаточн\w*|непереносимост\w* лактозы|галактоземи\w*|глюкозо-галактозн\w*', re.IGNORECASE),
    'alcohol': re.compile(r'злоупотребл\w* алкогол\w*|употребл\w* алкогол\w*|алкогол\w* (?:еженедельно|ежедневно|регулярно|по выходным)|пь[её]т (?:пиво|вино|крепкие)', re.IGNORECASE),
    'driving': re.compile(r'водител\w*|водит (?:автомобил|машин)\w*|управля\w* (?:автомобил|транспорт)\w*|за рул[её]м|работ\w* с механизм\w*|машинист\w*|диспетчер\w*', re.IGNORECASE),
}

DRUG_CLASSES: dict[str, tuple[str, ...]] = {
    'serotonergic_drugs': ('сертралин', 'эсциталопрам', 'циталопрам', 'флуоксетин', 'пароксетин', 'флувоксамин', 'венлафаксин', 'дулоксетин', 'милнаципран',
                           'кломипрамин', 'амитриптилин', 'имипрамин', 'тразодон', 'вортиоксетин', 'агомелатин', 'трамадол', 'суматриптан', 'золмитриптан', 'литий', 'зверобой'),
    'cyp2d6_inhibitors': ('флуоксетин', 'пароксетин', 'бупропион', 'хинидин', 'тербинафин', 'дулоксетин', 'мирабегрон', 'циннакалцет'),
    'maoi_recent': ('моклобемид', 'селегилин', 'разагилин', 'линезолид', 'пирлиндол', 'ипрониазид', 'транилципромин'),
    'sedatives': ('феназепам', 'бромдигидрохлорфенилбензодиазепин', 'диазепам', 'алпразолам', 'лоразепам', 'клоназепам', 'нитразепам', 'оксазепам', 'тофизопам',
                  'золпидем', 'зопиклон', 'кветиапин', 'гидроксизин', 'атаракс', 'дифенгидрамин', 'хлорпромазин', 'миртазапин', 'прегабалин', 'габапентин', 'фенобарбитал', 'корвалол'),
}
KNOWN_DRUGS = sorted({name for names in DRUG_CLASSES.values() for name in names} | {
    'авиандр', 'маритупирдин', 'арипипразол', 'оланзапин', 'рисперидон', 'вальпроевая кислота', 'вальпроат', 'карбамазепин', 'ламотриджин',
    'метформин', 'левотироксин', 'эналаприл', 'лизиноприл', 'амлодипин', 'бисопролол', 'аторвастатин', 'омепразол', 'ибупрофен', 'парацетамол',
    'этилметилгидроксипиридина сукцинат', 'мексидол', 'фенибут', 'афобазол', 'фабомотизол', 'буспирон', 'мелатонин', 'глицин', 'пирацетам',
}, key=len, reverse=True)

DIAGNOSIS_NAMES = (
    (re.compile(r'генерализованн\w* тревожн\w* расстройств\w*|\bгтр\b', re.IGNORECASE), 'F41.1'),
    (re.compile(r'смешанн\w* тревожн\w* и депрессивн\w* расстройств\w*', re.IGNORECASE), 'F41.2'),
    (re.compile(r'паническ\w* расстройств\w*', re.IGNORECASE), 'F41.0'),
    (re.compile(r'рекуррентн\w* депрессивн\w* расстройств\w*|\bрдр\b', re.IGNORECASE), 'F33'),
    (re.compile(r'депрессивн\w* эпизод\w*', re.IGNORECASE), 'F32'),
    (re.compile(r'расстройств\w* адаптаци\w*', re.IGNORECASE), 'F43.2'),
)
ICD_RE = re.compile(r'\b([A-ZА-Я])\s?(\d{2})(?:\.(\d{1,2}))?\b')
ICD_CYRILLIC = {'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H', 'О': 'O', 'Р': 'P', 'С': 'C', 'Т': 'T', 'Х': 'X', 'F': 'F', 'Ф': 'F', 'Г': 'G', 'И': 'I', 'Ж': 'J', 'Л': 'L', 'Д': 'D', 'Ц': 'C', 'Ю': 'U'}
SCALE_RE = {
    'phq9': (re.compile(r'(?:phq[\s-]?9|пхк[\s-]?9|опросник здоровья пациента)\D{0,25}?(\d{1,2})(?!\d)', re.IGNORECASE), 27),
    'gad7': (re.compile(r'(?:gad[\s-]?7|гтр[\s-]?7|шкала тревоги gad)\D{0,25}?(\d{1,2})(?!\d)', re.IGNORECASE), 21),
}
DURATION_RE = re.compile(
    r'(?:в течение|на протяжении|около|последние|последних|более|менее|уже|около)\s+(?:(\d+(?:[,.]\d+)?|одн\w*|двух|тр[её]х|четыр\w*|пол\w*|нескольк\w*)\s+)?(дн\w*|недел\w*|месяц\w*|мес\.?|год\w*|лет)'
    r'|(\d+(?:[,.]\d+)?)\s*(?:-|–)?\s*(?:х\s+)?(недел\w*|месяц\w*|мес\.?|лет|год\w*)\s+назад'
    r'|с\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(?:\d{4}\s*г?\.?)?',
    re.IGNORECASE,
)
DOSE_RE = re.compile(r'(\d+(?:[,.]\d+)?)\s*(мг|мкг|г|мл|ед)\b', re.IGNORECASE)
SCHEDULE_RE = re.compile(r'(\d)\s*(?:р(?:аза?)?\.?\s*/?\s*(?:в\s*)?(?:д|день|сут\w*)\.?)|утром|вечером|на ночь|днём|днем|по требованию|1-0-1|1-0-0|0-0-1|1-1-1', re.IGNORECASE)


def extract_text(content: bytes, filename: str = '') -> str:
    if len(content) > MAX_BYTES:
        raise ValueError('Файл больше 5 МБ')
    if filename.lower().endswith('.pdf') or content[:5] == b'%PDF-':
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(content))
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        except Exception as error:  # повреждённый PDF не должен ронять сервер
            raise ValueError('Не удалось прочитать PDF') from error
        if not text.strip():
            raise ValueError('В PDF нет текстового слоя (похоже на скан); вставьте текст вручную')
        return text
    for encoding in ('utf-8-sig', 'cp1251'):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('Не удалось определить кодировку текста')


def _normalize(text: str) -> str:
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace(' ', ' ').replace('ё', 'е').replace('Ё', 'Е')
    text = re.sub(r'[ \t]+', ' ', text)
    # «…19 лет. Жалобы: …» — заголовок посреди строки переносим на новую строку
    return INLINE_HEADER_RE.sub('\n', text)


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = None
    alias_map = {alias.replace('ё', 'е'): key for alias, key in HEADER_ALIASES}
    for raw in text.split('\n'):
        line = raw.strip().strip('*_').strip()
        match = HEADER_RE.match(line)
        if match:
            name = match.group('name').lower()
            rest = match.group('rest').strip()
            # «Принимает сертралин» без разделителя — это фраза, а не заголовок
            if match.group('sep') or not rest:
                key = alias_map.get(name, name)
                sections.setdefault(key, [])
                if rest:
                    sections[key].append(rest)
                # «Аллергии: пенициллин» — короткий раздел в одну строку; следующие строки ему не принадлежат
                current = None if rest and key in SHORT_SECTIONS else key
                continue
        if current and line:
            sections[current].append(line)
    return {key: ' '.join(lines).strip() for key, lines in sections.items() if ' '.join(lines).strip()}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r'(?<=[.!?;])\s+|\n+', text) if part.strip()]


def _mentions(pattern: re.Pattern[str], text: str) -> tuple[bool | None, str]:
    """True — есть утвердительное упоминание, False — только отрицаемое, None — не упоминается."""
    negative = ''
    for sentence in _sentences(text):
        previous_negated = False
        for clause in re.split(r'[,;]\s*', sentence):
            found = pattern.search(clause)
            # отрицание ищем вне найденного выражения: «не хочет жить» — это не отрицание риска
            negated = bool(NEGATION.search(clause.replace(found.group(0), ' ') if found else clause))
            # «Галлюцинаций не выявлено, бреда» — короткое продолжение перечисления наследует отрицание
            if not negated and previous_negated and len(clause.split()) <= 3:
                negated = True
            if found:
                if negated:
                    negative = negative or sentence
                else:
                    return True, sentence
            previous_negated = negated
    return (False, negative) if negative else (None, '')


def _age(text: str) -> int | None:
    match = re.search(r'(?:возраст\s*[:\-|]?\s*)(\d{1,3})|\b(\d{2})\s*(?:лет\b|год(?:а)?\b|л\.)(?!\s*назад)', text, re.IGNORECASE)
    if match:
        value = int(match.group(1) or match.group(2))
        if 14 <= value <= 110:
            return value
    birth = re.search(r'(?:дата рождения|д\.\s*р\.|г\.р\.?|родил\w*)\s*[:\-]?\s*(\d{2})\.(\d{2})\.(\d{4})', text, re.IGNORECASE)
    if birth:
        born = date(int(birth.group(3)), int(birth.group(2)), int(birth.group(1)))
        today = date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return None


def _sex(text: str) -> str | None:
    if re.search(r'[а-я]+(?:овна|евна|ична|инична)\b|\bпол\s*[:\-]?\s*ж|\bженщин\w*|\bпациентк\w*|\bбеременн', text, re.IGNORECASE):
        return 'female'
    if re.search(r'[а-я]+(?:ович|евич|ьич)\b|\bпол\s*[:\-]?\s*м|\bмужчин\w*|\bпациент\s+\w+ов\b|\bмужск\w*', text, re.IGNORECASE):
        return 'male'
    return None


def _icd_codes(text: str) -> list[str]:
    codes = []
    for letter, major, minor in ICD_RE.findall(text):
        latin = ICD_CYRILLIC.get(letter, letter)
        if not latin.isascii() or not latin.isalpha():
            continue
        code = f'{latin}{major}' + (f'.{minor}' if minor else '')
        if latin == 'F' or re.search(r'мкб|диагноз|ds|сопутств', text, re.IGNORECASE):
            codes.append(code)
    return list(dict.fromkeys(codes))


def _medications(section: str, full_text: str) -> list[dict[str, str]]:
    source = section or full_text
    found = []
    lowered = source.lower()
    for name in KNOWN_DRUGS:
        for match in re.finditer(re.escape(name), lowered):
            start = match.start()
            if any(start >= item['_start'] and start < item['_end'] for item in found):
                continue
            window = source[start:start + 80].split('\n')[0]
            window = re.split(r'(?<=\S)[,;](?=\s*[А-ЯA-Zа-я]{4,}\s)', window)[0]
            # статус препарата определяем только по его фразе: до ближайших «. », «;», «,» или переноса строки
            begin = max(source.rfind(mark, 0, start) for mark in ('. ', ';', ',', '\n')) + 1
            ends = [position for position in (source.find(mark, start) for mark in ('. ', ';', '\n')) if position != -1]
            phrase = source[begin:min(ends) if ends else len(source)]
            before = source[begin:start]
            if NEGATION.search(before) and 'отмен' not in phrase.lower():
                continue
            dose = DOSE_RE.search(window)
            schedule = SCHEDULE_RE.search(window)
            stopped = bool(re.search(r'отмен\w*|прекрат\w*|ранее|в прошлом', phrase, re.IGNORECASE))
            found.append({'name': name, 'dose': ' '.join(dose.groups()) if dose else '', 'schedule': schedule.group(0) if schedule else '',
                          'status': 'stopped' if stopped else 'current', '_start': start, '_end': start + len(name)})
    found.sort(key=lambda item: item['_start'])
    return [{key: value for key, value in item.items() if not key.startswith('_')} for item in found]


def _duration(*texts: str) -> str:
    for text in texts:
        match = DURATION_RE.search(text or '')
        if match:
            return match.group(0).strip()
    return ''


def parse(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError('Пустой текст истории болезни')
    text = _normalize(text)
    sections = split_sections(text)
    evidence: dict[str, str] = {}
    warnings: list[str] = []

    complaints = sections.get('complaints', '')
    history = ' '.join(part for part in (sections.get('history', ''), sections.get('life_history', '')) if part)
    diagnosis = sections.get('diagnosis', '')
    allergies = sections.get('allergies', '')
    first_allergy = _sentences(allergies)[0] if allergies else ''
    if first_allergy and NEGATION.search(first_allergy) and not re.search(r'аллерги\w* на|непереносим|реакци', first_allergy, re.IGNORECASE):
        allergies = 'Не отягощён'

    self_harm, self_harm_evidence = _mentions(SELF_HARM, text)
    psychosis, psychosis_evidence = _mentions(PSYCHOSIS, text)
    if self_harm_evidence:
        evidence['self_harm_concern'] = self_harm_evidence
    if psychosis_evidence:
        evidence['psychosis_signs'] = psychosis_evidence

    sex = _sex(text)
    pregnant, pregnancy_evidence = _mentions(re.compile(r'беременн\w*', re.IGNORECASE), text)
    if re.search(r'беременн[^.\n]{0,40}(?:' + UNCERTAIN + r')|не\s+исключ\w*[^.\n]{0,20}беременн', text, re.IGNORECASE):
        pregnant = None
    pregnancy_status = 'yes' if pregnant else 'no' if pregnant is False else 'not_applicable' if sex == 'male' else 'unknown'
    if pregnancy_evidence:
        evidence['pregnancy_status'] = pregnancy_evidence

    medications = _medications(sections.get('current_medications', ''), text)
    current_names = {item['name'] for item in medications if item['status'] == 'current'}
    recent_names = {item['name'] for item in medications}
    factors: dict[str, bool] = {'pregnancy': pregnancy_status == 'yes'}
    for key, pattern in FACTOR_PATTERNS.items():
        value, snippet = _mentions(pattern, text)
        factors[key] = bool(value)
        if value and snippet:
            evidence[key] = snippet
    egfr = re.search(r'(?:скф|egfr|клиренс креатинина)\D{0,20}?(\d{1,3})', text, re.IGNORECASE)
    factors['egfr_below_60'] = bool(egfr and int(egfr.group(1)) < 60)
    if egfr:
        evidence['egfr_below_60'] = egfr.group(0)
    for key, names in DRUG_CLASSES.items():
        pool = recent_names if key == 'maoi_recent' else current_names
        hits = sorted(pool & set(names))
        factors[key] = bool(hits)
        if hits:
            evidence[key] = ', '.join(hits)

    scales = {}
    for scale_id, (pattern, maximum) in SCALE_RE.items():
        match = pattern.search(text)
        if match:
            value = int(match.group(1))
            if value <= maximum:
                scales[scale_id] = value
            else:
                warnings.append(f'{scale_id.upper()}: значение {value} вне диапазона 0–{maximum}, пропущено')

    codes = _icd_codes(diagnosis or text)
    if not any(code.startswith('F') for code in codes):
        for pattern, code in DIAGNOSIS_NAMES:
            if pattern.search(diagnosis or text):
                codes.insert(0, code)
                warnings.append(f'Код {code} определён по названию диагноза, проверьте')
                break
    if not sections:
        warnings.append('Разделы не распознаны: поля заполнены по всему тексту, проверьте внимательно')
    if self_harm:
        warnings.append('Есть упоминание суицидальных мыслей или самоповреждения — требуется оценка риска врачом')

    medication_text = '; '.join(
        ' '.join(part for part in (item['name'].capitalize(), item['dose'], item['schedule']) if part) + (' (отменён)' if item['status'] == 'stopped' else '')
        for item in medications
    )
    fields = {
        'visit_reason': sections.get('visit_reason', '')[:500],
        'complaints': complaints[:4000],
        'symptom_duration': _duration(complaints, history, text)[:300],
        'history': history[:6000],
        'comorbidities': sections.get('comorbidities', '')[:3000],
        'current_medications': (medication_text or sections.get('current_medications', ''))[:3000],
        'allergies': allergies[:2000],
        'working_hypothesis': (diagnosis or ', '.join(codes))[:1000],
        'psychosis_signs': bool(psychosis),
        'self_harm_concern': bool(self_harm),
        'pregnancy_status': pregnancy_status,
    }
    return {
        'fields': fields,
        'age': _age(text),
        'sex': sex,
        'icd_codes': codes,
        'scales': scales,
        'medications': medications,
        'therapy_factors': factors,
        'sections_found': sorted(sections),
        'evidence': evidence,
        'warnings': warnings,
        'characters': len(text),
    }
