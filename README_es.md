# Accessible Text Analyst

Un pipeline de PLN multilingüe diseñado para la **accesibilidad con lectores de pantalla** (NVDA, JAWS, VoiceOver, Narrador). Todo el código, la salida de consola y los informes están pensados para que la tecnología de apoyo los interprete con limpieza: sin colores ANSI, sin emoji, sin barras de progreso, sin caracteres de dibujo de recuadros.

> **Otros idiomas:** [English](README.md) · [polski](README_pl.md) · [русский](README_ru.md) · [suomi](README_fi.md) · [íslenska](README_is.md) · [italiano](README_it.md) · [Deutsch](README_de.md) · [français](README_fr.md)

> **Estado de la traducción (v1.0).** Solo se ha traducido el README. La narración del notebook de Jupyter, toda la salida de consola, `CLAUDE.md` y los comentarios del código siguen en sus idiomas originales (sobre todo ruso, con polaco en los parches y en la capa chamánica). Su traducción está prevista deliberadamente para la v1.1 — consulta `release_notes.md`.

## Contenido del proyecto

- `accessible_text_analyst.ipynb` — un notebook de Jupyter con el pipeline de análisis completo (42 celdas: 21 de código + 21 de markdown; la narración del notebook está en ruso). Escribe dos artefactos accesibles (`accessible_text.html`, `accessible_text.docx`) en los que cada párrafo y cada frase en otro idioma llevan su propio atributo `lang`, de modo que los lectores de pantalla y los motores TTS cambian de voz automáticamente — incluso sin conexión.
- `generate_report.py` — un script de posprocesado que convierte el notebook ejecutado en un único archivo HTML accesible (`analysis_report.html`). Envuelve los fragmentos de un corpus en otro idioma en `<span lang="target_lang">` y, sea cual sea el idioma del corpus, pone siempre `<span lang="en">` alrededor del contenido técnico en inglés (etiquetas POS, etiquetas NER, identificadores de modelos de spaCy/Hugging Face, nombres de archivo ASCII). El código en línea y los bloques de código de la narración se etiquetan en bloque con `lang="en"`. En el modo de lectura (`remove_noise: true`) recorta los bucles de diagnóstico por documento del notebook a los primeros documentos en lugar de volcar cientos de ellos.
- `run_all.py` — un lanzador para toda la cadena local gratuita: registra el kernel de Jupyter `analyst_env` si falta, ejecuta el notebook sin interfaz (sin la celda interactiva de preguntas) y guarda sus salidas en el `.ipynb`, y después ejecuta `generate_report.py`, `shamanic_pipeline.py` y, para un corpus finlandés, el `scan` del Libro de lo No Dicho. Nunca lanza un paso de pago (rituales LLM, voces de ElevenLabs, `draft`/`fill` del Libro).
- `generate_diagnostic.py` — un generador independiente de un **informe de diagnóstico** completo (`diagnostic_report.html`) construido directamente a partir de las exportaciones CSV/JSON del notebook (no a partir de la salida de `generate_report.py`). Una estructura navegable y pensada ante todo para lectores de pantalla: un índice en `<nav>` y secciones — cada una con su propio encabezado y listas — para un resumen general, los temas con sus párrafos, las tesis, las entidades nombradas agrupadas por tipo y las palabras clave principales. Las etiquetas estructurales siguen `ui_lang`; los fragmentos del corpus reciben `<span lang="…">`, las etiquetas NER `<span lang="en">`.
- `generate_md.py` — convierte el `analysis_report.html` generado en `gemini_notebook_report.md` para cargarlo en Gemini Notebook (antes NotebookLM). Los spans de accesibilidad se eliminan, ya que Gemini Notebook no los aprovecha.
- `shamanic_pipeline.py` *(opcional)* — un posprocesador sin LLM que convierte las exportaciones CSV/JSON del notebook en artefactos de texto rituales (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt` y — cuando el análisis de sentimiento opcional está activado — `emotional_undertow.txt`), totalmente localizados en los nueve idiomas admitidos.
- `shamanic_ai.py` *(opcional, basado en LLM)* — llama a un LLM (OpenAI por defecto; OpenRouter o cualquier endpoint compatible con OpenAI mediante `llm_provider`) para generar cuatro voces narrativas (`Katla`, `Vieno`, `Lumi`, `Sami`) sobre las mismas exportaciones. Cuando existe el `sentiment.csv` opcional, Vieno construye su canto sobre el arco emocional del texto en lugar de sobre frases crudas. Requiere la clave del proveedor elegido en `golden_key.env`.
- `shamanic_voice.py` *(opcional, requiere ElevenLabs)* — un despachador independiente de una sola ejecución que sintetiza en audio `.mp3` los cuatro artefactos narrativos producidos por `shamanic_ai.py` mediante la API de ElevenLabs, registra en la consola cada éxito o fallo y termina (sin bot, sin servidor). Necesita `ELEVENLABS_API_KEY` en `golden_key.env` y una asignación `voices` en la configuración.
- `shamanic_locale.py` — el paquete de localización de ambos scripts chamánicos (plantillas, encabezados y textos de reserva de Lumi en los nueve idiomas admitidos).
- `ksiega_niedomowien.py` *(opcional, solo finlandés, asistido por un agente)* — el Libro de lo No Dicho (*Sanomattomien kirja*): convierte `raw_roots_chant.txt` en un diario críptico que crece poco a poco y cuyos huecos no supo adivinar un modelo ciego. Es el ayudante determinista de la skill de `skills/ksiega-niedomowien/SKILL.md`; su salida de consola sigue `ui_lang`.
- `helsinki_reacts.py` *(opcional, con LLM)* — guion satírico de un directo: Valtteri, de Helsinki, reacciona con un chat finlandés a una grabación (una carpeta de exportación o un archivo de texto). El prompt de sistema está fuera del código (`helsinki_reacts.example.md`; tu propia copia, en `helsinki_reacts.md`) y el idioma del directo sigue a `reacts_lang` y después a `ui_lang`. Requiere la clave del proveedor elegido en `golden_key.env`.

## Qué hace el pipeline

1. Carga texto de un archivo (`.pdf`, `.txt`, `.docx`, `.md`, `.html` o imágenes: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) o de una URL — eliminando encabezados y pies de página repetidos, barras laterales, secciones de «Artículos relacionados» y textos repetitivos parecidos. Los PDF escaneados y las imágenes recurren al OCR: cada idioma de `corpus_languages` lee la página con su propio motor (el OCR integrado en Windows 10/11, o Tesseract para un idioma que Windows no tiene — hoy el islandés), RapidOCR la lee una vez más como respaldo, y un diccionario de cada idioma elige las formas de diccionario de entre todas las lecturas. En un `.docx`, las tablas, los cuadros de texto y las imágenes insertadas se leen en el orden del documento: una imagen aporta su texto alternativo, una imagen sin él la lee el mismo OCR (una vez por archivo de imagen, aunque se repita) y cada imagen que no se pudo leer se indica por su número. Los encabezados, los pies de página, los gráficos y SmartArt no se leen, pero el resumen de la carga indica cuántos hay (el texto alternativo de un gráfico sí entra en el texto); las eliminaciones con control de cambios se omiten y las inserciones se leen.
2. Decide el idioma de cada palabra a partir de los diccionarios de los idiomas enumerados en `corpus_languages` (ver **El idioma de cada palabra**): el idioma base dirige el pipeline de spaCy, y las citas y los nombres en otros idiomas se convierten en segmentos lingüísticos.
3. Ejecuta spaCy una vez por segmento de texto: el modelo del idioma base procesa el texto base junto con los segmentos extranjeros insertados, y cada bloque extranjero lo procesa el modelo de su propio idioma, cargado bajo demanda mediante `get_nlp()` (envuelto en `functools.lru_cache(maxsize=2)`, de modo que como máximo hay dos modelos en caché). No hay pasada de resegmentación ni segunda pasada multilingüe.
4. Tokenización → filtrado de palabras vacías → lematización → etiquetado POS → NER, cada token analizado por el modelo de su propio idioma.
5. Representaciones vectoriales: Bag of Words, TF-IDF + búsqueda con consulta automática y clasificación por coseno.
6. Estructura: frases → párrafos (de 3 a 6 frases cada uno) → tesis (la mejor frase de cada párrafo). Cada frase lleva su idioma y sus segmentos extranjeros insertados; cada párrafo lleva su idioma predominante.
7. Modelado de temas con KMeans sobre los vectores de párrafo de spaCy.
8. *(Opcional, desactivado por defecto)* Puntuación de sentimiento por párrafo con `cardiffnlp/twitter-xlm-roberta-base-sentiment`, escrita en `sentiment.csv`. El resultado nunca se muestra al usuario — existe solo como alimento para la capa chamánica. Ver **Configuración** (`enable_sentiment`).
9. Exportación CSV/JSON + un informe textual de resumen + una exportación HTML y DOCX etiquetada para accesibilidad + un informe HTML global (`analysis_report.html`).

## Idiomas admitidos

| Código | Idioma     | Modelo de spaCy        | NER / vectores |
|------|------------|------------------------|----------------|
| pl   | polaco     | `pl_core_news_lg`      | spaCy          |
| ru   | ruso       | `ru_core_news_lg`      | spaCy          |
| en   | inglés     | `en_core_web_lg`       | spaCy          |
| it   | italiano   | `it_core_news_lg`      | spaCy          |
| de   | alemán     | `de_core_news_lg`      | spaCy          |
| es   | español    | `es_core_news_lg`      | spaCy          |
| fr   | francés    | `fr_core_news_lg`      | spaCy          |
| fi   | finlandés  | `fi_core_news_lg`      | spaCy          |
| is   | islandés   | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT` (vectores), `grammatek/icelandic-ner-bert` (NER) |

No existe un modelo completo de spaCy para el islandés, así que se conectan dos modelos de Hugging Face a un pipeline vacío. La primera descarga necesita ~1,3 GB de disco y conexión a internet; las ejecuciones posteriores reutilizan la caché de HF.

**Mejora opcional de la morfología finlandesa (omorfi).** El lematizador estadístico de `fi_core_news_lg` se las ve con dificultad con la morfología aglutinante del finlandés — produce habitualmente lemas basura como *kytköknen* o *pisttää*. Cuando el paquete en Python puro `omorfi` está instalado y sus autómatas FST descargados (ver el paso 5 de la instalación), el notebook añade un componente `omorfi_lemmas` que sustituye los lemas y los rasgos morfológicos UD por análisis de diccionario siempre que coincidan con la categoría gramatical del etiquetador de spaCy (`kytköksistä` → `kytkös`, `Euroopassa` → `Eurooppa`, `pistät` → `pistää`). Sin el paquete o sin los autómatas, el pipeline mantiene en silencio el comportamiento estándar de spaCy.

## El idioma de cada palabra

Enumeras los idiomas del texto en `corpus_languages` (`config.json`; el nombre antiguo `ocr_languages` se sigue leyendo). A partir de los diccionarios de esos idiomas, el notebook decide:

1. **Idioma base** (`LANG`) — el idioma cuyo diccionario conoce la mayor proporción de palabras del corpus (las proporciones se imprimen). Dirige el pipeline principal de spaCy.
2. **El idioma de cada palabra** (`odcinki_jezykowe.py`). Una palabra que el diccionario base no conoce pero sí otro idioma enumerado pertenece a ese idioma; una palabra que conocen varios va al alfabeto más pequeño que contiene todas sus letras — así una palabra inglesa no se la queda el diccionario polaco, que conoce muchas formas inglesas, mientras que `Łódź` sigue siendo polaca. La escritura es un hecho: una palabra cirílica en un texto latino recibe un idioma cirílico aunque no se haya enumerado ninguno.
3. **Segmentos extranjeros** — al menos dos palabras extranjeras seguidas de un mismo idioma dentro de una frase, o una palabra con letras que le faltan al alfabeto base. Un segmento que abarca frases enteras es un **bloque** y lo procesa su propio modelo de spaCy (frases, NER, lemas). Un segmento dentro de una frase en el idioma base es un **segmento insertado**: la frase se queda con el modelo base, y el segmento recibe sus lemas y etiquetas POS del modelo de su propio idioma.

La exportación lleva el resultado: `<span lang="…">` en `accessible_text.html` y un `Run` aparte con `<w:lang>` en `accessible_text.docx` para cada frase extranjera y cada segmento insertado, de modo que el lector de pantalla cambia de voz exactamente en la cita o en el nombre, no en toda la frase. Todos los segmentos se enumeran también en `language_spans.csv`, y `sentences.csv` tiene una columna `lang`.

Diccionarios: vectores de spaCy (una lista finita de formas) para el polaco, el inglés, el ruso, el italiano, el alemán, el español y el francés; `omorfi` para el finlandés; BÍN (`islenska`) para el islandés — los mismos diccionarios que usa la votación del OCR. Con un solo idioma en `corpus_languages` no se carga ningún diccionario y solo se etiquetan las palabras de otra escritura. Un diccionario ausente detiene la ejecución con un mensaje que indica cómo arreglarlo.

**Qué idiomas enumerar.** Medido sobre 20 transcripciones finlandesas (55 000 palabras) que mencionan muchos nombres polacos: con `["fi", "en"]` el notebook encuentra 34 segmentos ingleses (términos y citas); con `["fi", "pl", "en"]` encuentra además 57 segmentos polacos — nombres polacos y algunas expresiones polacas, que ahora lee una voz polaca en lugar de una finlandesa — y ninguna palabra inglesa va a parar al polaco. Por tanto:

- enumera todos los idiomas cuyas **citas** aparecen en el texto;
- para un texto escrito en un idioma que menciona **nombres** de otro (nombres polacos en un texto finlandés), añade el idioma de los nombres: los nombres en su forma base, y los nombres con letras que le faltan al alfabeto base (`ł`, `ś`), los lee entonces la voz de su propio idioma. Un nombre declinado solo con letras del alfabeto base (`Kowalskille`) se queda en el idioma base en cualquier caso;
- no enumeres un idioma que no aparece en el texto: solo añade candidatos falsos.

**Por qué no un detector estadístico.** Hasta ATA 1.x, `lingua-language-detector` clasificaba frases enteras. Sobre las mismas transcripciones marcó 127 frases como extranjeras, casi todas por error; las heurísticas de protección necesarias para suprimirlo dejaban 2 frases y ninguna de las citas inglesas. ATA 2.0 lo eliminó. El informe global (`generate_report.py`) etiqueta las palabras extranjeras de su narración rusa con los mismos diccionarios (los idiomas de `corpus_languages` más el inglés).

## Requisitos

- Python 3.12 o posterior (el conjunto de dependencias está probado con Python 3.14).
- ~1,5 GB de disco libre para los modelos `_lg` de spaCy (uno por cada idioma que instales). Suma ~1,3 GB si activas el islandés (Hugging Face `transformers` + `torch` + IceBERT + icelandic-ner-bert). El NER islandés lee todo el documento en ventanas solapadas: unos 4000 caracteres por segundo en CPU, así que un libro (1 MB de texto islandés) tarda unos minutos.
- Soporte de OCR (opcional): los paquetes `winrt-*` (menos de 1 MB) y, para cada idioma de `corpus_languages`, el paquete de idioma de Windows con reconocimiento óptico de caracteres (Configuración > Hora e idioma > Idioma y región); `rapidocr` con `onnxruntime` (sus modelos, unos 40 MB, se descargan en la primera llamada al OCR); para un idioma sin motor de Windows (hoy el islandés), `tesserocr` y el modelo tessdata_best de ese idioma en la carpeta `tessdata` del repositorio (islandés: https://github.com/tesseract-ocr/tessdata_best/raw/main/isl.traineddata, unos 9,5 MB) más el diccionario `islenska` (~62 MB). El OCR ya no necesita `torch`. Un motor o un diccionario ausente detiene la ejecución con un mensaje que indica cómo arreglarlo. Diccionario islandés: The Database of Icelandic Morphology (BÍN), The Árni Magnússon Institute for Icelandic Studies, autora y editora Kristín Bjarnadóttir, CC BY-SA 4.0.
- Suma ~130 MB si activas la mejora de la morfología finlandesa (los autómatas FST de `omorfi` que descarga `omorfi-download`).
- Conexión a internet en la primera ejecución (descarga de modelos).

## Preparación del entorno

Elige una de las tres opciones siguientes. Las tres terminan con el mismo `pip install -r requirements.txt` + descargas de modelos de spaCy.

### Opción A — `venv` local (recomendada para el uso diario)

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

El directorio `.venv/` está en `.gitignore`. Dentro del venv activado, continúa con **Instalación** más abajo.

### Opción B — Anaconda / Miniconda

```bash
conda create -n accessible-text-analyst python=3.14
conda activate accessible-text-analyst
```

Después continúa con **Instalación** más abajo. El `pip` incluido en Anaconda funciona sin problemas — no hay una lista de paquetes específica de Conda para este proyecto.

### Opción C — Google Colab (sin instalación local)

Abre un notebook nuevo de Colab y pega lo siguiente en la primera celda. Esto clona el repositorio, instala las dependencias y descarga los modelos de spaCy que necesitas.

```python
!git clone https://github.com/<your-fork>/accessible_text_analyst.git
%cd accessible_text_analyst
!pip install -r requirements.txt
!python -m spacy download en_core_web_lg
# Añade las líneas siguientes solo para los idiomas que de verdad necesites:
# !python -m spacy download pl_core_news_lg
# !python -m spacy download ru_core_news_lg
# !python -m spacy download it_core_news_lg
# !python -m spacy download fi_core_news_lg
# !python -m spacy download de_core_news_lg
# !python -m spacy download es_core_news_lg
# !python -m spacy download fr_core_news_lg
```

Después sube tu `config.json` (o `config.ini`) desde el panel Archivos, define `source_file` y ejecuta el notebook. Nota: las sesiones de Colab son efímeras — los modelos descargados y los artefactos de `export_results/` desaparecen cuando se recicla el entorno de ejecución. Para análisis largos, monta Google Drive y escribe allí la salida.

## Instalación

```bash
# 1. Dependencias de Python
pip install -r requirements.txt

# 2. Modelos de spaCy — instala solo los idiomas que de verdad necesites.
# Las variantes *_lg son necesarias porque el modelado de temas depende de los vectores de palabras.
python -m spacy download pl_core_news_lg
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
python -m spacy download fi_core_news_lg
python -m spacy download de_core_news_lg
python -m spacy download es_core_news_lg
python -m spacy download fr_core_news_lg

# 3. (Opcional) Soporte del islandés — descomenta `transformers` y `torch`
# en requirements.txt y vuelve a ejecutar `pip install -r requirements.txt`.
# IceBERT e icelandic-ner-bert se descargan entonces de Hugging Face en la primera ejecución.

# 4. (Opcional) Análisis de sentimiento — descomenta `transformers`, `torch`,
# `sentencepiece`, `protobuf` y `tiktoken` en requirements.txt, repite la
# instalación y pon "enable_sentiment": true en config.json. El modelo
# (~1,1 GB) se descarga de Hugging Face en la primera ejecución y queda en caché.
# Los cinco paquetes hacen falta a la vez para construir el tokenizador de XLM-RoBERTa.

# 5. (Opcional) Mejora de la morfología finlandesa — descomenta `omorfi` en
# requirements.txt, repite la instalación y después descarga los autómatas FST
# (~130 MB de archivos *.hfst descomprimidos en la raíz del repositorio; están en .gitignore).
# Ejecútalo desde la raíz del repositorio:
omorfi-download

# 6. (Opcional) Compara las versiones instaladas con los límites de
# requirements.txt y con PyPI. Solo advierte, nunca bloquea:
python audyt_zaleznosci.py
```

## Configuración

Copia la configuración de ejemplo a un archivo local. Se aceptan tanto `config.json` como `config.ini` — **el contenido del archivo es JSON en ambos casos**; la extensión `.ini` es solo una concesión práctica a los usuarios de Windows sin perfil técnico, para quienes `.json` no tiene programa asociado.

```bash
# Elige uno:
cp config.example.json config.json
cp config.example.ini  config.ini
```

`config.json` y `config.ini` están ambos en `.gitignore`, así que cada usuario conserva su propia copia local.

Contenido:

```json
{
  "source_file": "C:/path/to/document.pdf",
  "custom_patterns": [],
  "remove_noise": true,
  "corpus_languages": ["en"],
  "enable_sentiment": false,
  "ui_lang": "",
  "lumi_katla_lines": null,
  "lumi_vieno_lines": null,
  "llm_provider": "",
  "llm_model": "",
  "llm_base_url": "",
  "kirja_llm_provider": "",
  "kirja_drafter_model": "",
  "kirja_filler_model": "",
  "reacts_llm_provider": "",
  "reacts_model": "",
  "reacts_lang": "",
  "voices": {
    "katla": "",
    "vieno": "",
    "lumi": "",
    "sami": ""
  }
}
```

| Clave              | Tipo            | Finalidad |
|--------------------|-----------------|---------|
| `source_file`      | string          | Ruta a un archivo (`.pdf`, `.txt`, `.docx`, `.md`, `.html` o una imagen) **o** una URL (`http://`, `https://`). Una cadena vacía o un archivo inexistente recurren al corpus de ejemplo integrado. |
| `custom_patterns`  | string[]        | Expresiones regulares opcionales que se eliminan del texto bruto (titulillos, pies de página, textos repetitivos). Ejemplo: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Alterna `generate_report.py` entre el modo de lectura (`true`, oculta las barras de carga de Hugging Face/torch y las tablas de lematización/POS) y el modo de diagnóstico completo (`false`). |
| `corpus_languages` | string[]        | Idiomas del TEXTO (códigos de los paquetes de idioma: `de`, `en`, `es`, `fi`, `fr`, `is`, `it`, `pl`, `ru`); el nombre antiguo `ocr_languages` se sigue leyendo. Sus diccionarios eligen el idioma base y el idioma de cada palabra (ver **El idioma de cada palabra**), y en los PDF escaneados y las imágenes cada uno lee la página con su propio motor de OCR. Enumera solo los idiomas que de verdad aparecen en el texto: un idioma de más ralentiza el OCR y añade candidatos falsos. Se pueden mezclar escritura latina y cirílica (`["fi", "ru"]`). |
| `enable_sentiment` | boolean         | Activa el análisis de sentimiento opcional por párrafo (`false` por defecto). Requiere las dependencias de sentimiento comentadas (ver el paso 4 de la instalación). Escribe `sentiment.csv`; el resultado nunca se muestra al usuario, solo alimenta la capa chamánica (el ritual `emotional_undertow.txt` y el canto de Vieno). Ante cualquier fallo de carga se omite en silencio — sin alternativa. |
| `ui_lang`          | string          | Idioma de la interfaz para la salida de consola y el atributo `<html lang>` del informe generado (`pl` / `en` / `ru` / `fi` / `is` / `it` / `de` / `es` / `fr`). Cadena vacía o código desconocido → se recurre a `en`. Independiente del idioma del corpus analizado, que deciden los diccionarios de `corpus_languages`. |
| `lumi_katla_lines` | integer or null | Límite opcional del ornamento en el despacho de Lumi de `shamanic_ai.py`: cuántas líneas no vacías del monólogo de Katla ve Lumi. `null` o clave ausente = contenido completo; entero N > 0 = las primeras N líneas. |
| `lumi_vieno_lines` | integer or null | Igual que `lumi_katla_lines`, pero para el canto de ecos de Vieno. |
| `voices`           | object          | Asigna a cada voz chamánica (`katla` / `vieno` / `lumi` / `sami`) un ID de voz de ElevenLabs, que usa `shamanic_voice.py`. Una voz con ID vacío o ausente se omite. Solo es necesario si ejecutas el despachador de audio. |
| `llm_provider` | string | Proveedor LLM para `shamanic_ai.py` y el Libro: `openai` (por defecto), `openrouter` u `openai_compat`. Cada proveedor lee solo su propia clave de `golden_key.env` — ver *Proveedores LLM y claves* más abajo. |
| `llm_model` | string | Modelo para ese proveedor. Vacío = el modelo predeterminado del proveedor (`gpt-6.1-sol` / `openai/gpt-6.1-sol`); obligatorio para `openai_compat`. |
| `llm_base_url` | string | Dirección del endpoint, leída **solo** por `openai_compat` (p. ej. `http://localhost:1234/v1`). `openai` y `openrouter` la ignoran, porque sus direcciones son fijas. |
| `kirja_llm_provider` | string | Proveedor alternativo opcional para el Libro (`ksiega_niedomowien.py draft` / `fill`). Vacío = `llm_provider`. |
| `kirja_drafter_model` | string | Modelo para `draft` (el redactor por API del Libro). Vacío = el modelo predeterminado del proveedor, o `llm_model` cuando el Libro usa el proveedor global. |
| `kirja_filler_model` | string | Modelo para `fill` (el rellenador ciego de huecos del Libro). Misma alternativa que `kirja_drafter_model`. |
| `reacts_llm_provider` | string | Sustitución opcional del proveedor para `helsinki_reacts.py`. Vacío = `llm_provider`. |
| `reacts_model` | string | Modelo para `helsinki_reacts.py`. Vacío = el predeterminado del proveedor, o `llm_model` cuando Helsinki Reacts usa el proveedor global. |
| `reacts_lang` | string | Idioma del directo de `helsinki_reacts.py` (un código de `ui_lang`). Vacío = `ui_lang`. `fi` = el directo en finés; cualquier otro = su traducción con interjecciones en finés. |

> **Proveedores LLM y claves.** Una clave está ligada a un solo host y nunca se envía a otro sitio: `openai` → `OPENAI_API_KEY` → `api.openai.com`; `openrouter` → `OPENROUTER_API_KEY` → `openrouter.ai`; `openai_compat` → `LLM_COMPAT_API_KEY` → `llm_base_url`. El proveedor se elige explícitamente y nunca se deduce de una dirección, así que apuntar un script a otro servicio no puede filtrar la clave del primer servicio ni romper el otro script. La clave anterior a la v1.7.0 `kirja_filler_base_url` (que enviaba `OPENAI_API_KEY` a cualquier dirección) se rechaza con un mensaje de migración. En OpenRouter, los ID de modelo llevan un prefijo del fabricante (`openai/gpt-4o`, `anthropic/claude-sonnet-5.5`), y los ajustes de privacidad de la cuenta permiten excluir a los proveedores que puedan entrenar con tus prompts.

> **Análisis de sentimiento — coste de CPU.** Con `enable_sentiment: true`, la pasada por párrafo es pesada para la CPU — más o menos comparable a ejecutar en CPU el reconocimiento de voz local de Whisper. En equipos antiguos o con limitaciones térmicas esta carga sostenida puede castigar de verdad al procesador; actívalo a conciencia, idealmente en un equipo con GPU o con margen para trabajar a plena carga durante mucho tiempo.

> **`ui_lang` — alcance de la localización.** La salida de consola de los scripts independientes (`generate_report.py`, `generate_md.py`, `generate_diagnostic.py`, `shamanic_pipeline.py`, `shamanic_ai.py`, `ksiega_niedomowien.py`, `helsinki_reacts.py`) se localiza mediante `ui_lang`. La **salida del notebook no** se localiza — está fijada en ruso (solo el nombre del archivo de tesis sigue el idioma del corpus detectado). El `analysis_report.html` en modo de lectura conserva la narración rusa del notebook (su raíz es `<html lang="ru">`); el artefacto para el usuario totalmente localizado según `ui_lang` es **`diagnostic_report.html`**, producido por `generate_diagnostic.py`. Las traducciones en `fi` / `is` / `it` / `de` / `es` / `fr` son borradores sin revisar — comunica las asperezas en GitHub, por favor.

> **Rutas de Windows y expresiones regulares — importante.** El contenido de la configuración es JSON, y JSON no tiene sintaxis de cadenas sin escape. Una sola barra invertida escapa el carácter siguiente (`\U`, `\d`, `\n` son especiales), así que una ruta de Windows escrita como `"C:\Users\marek\doc.pdf"` producirá un error de análisis de JSON. Dos formas de escribirla bien:
>
> - **Barras normales** (lo más sencillo, funciona también en Windows): `"C:/Users/marek/doc.pdf"`.
> - **Barras invertidas dobles**: `"C:\\Users\\marek\\doc.pdf"`.
>
> La misma regla vale para cada expresión regular de `custom_patterns`: escribe `"\\d{4}"`, no `"\d{4}"`; escribe `"Copyright \\d{4}"`, no `"Copyright \d{4}"`. En JSON no existe la forma de cadena sin escape `r"…"`.

## Ejecución

Los scripts numerados a continuación están pensados para ejecutarse **en orden**: cada uno consume los artefactos que produjo el paso anterior.

### Atajo: toda la cadena local (`run_all.py`)

```bash
# notebook -> generate_report.py -> shamanic_pipeline.py -> escaneo del Libro (solo finlandés)
python run_all.py
# reutilizar las salidas ya guardadas en el notebook
python run_all.py --skip-notebook
# diagnóstico completo de las advertencias de bibliotecas, independiente de la configuración
python run_all.py --warnings-as-errors
```

Los pasos 1, 2 y 4 siguientes, más el `scan` del Libro de lo No Dicho para un corpus finlandés, con un solo comando. Ejecútalo con el Python del `.venv` del repositorio: si falta el kernel `analyst_env`, se registra para ese intérprete. La cadena se detiene en el primer paso que falla; el código de salida 3 significa que la comprobación de la fuente del informe rechazó la ejecución (ver el paso 2). El notebook silencia a propósito las advertencias de las bibliotecas para que no lleguen al informe de análisis. `--warnings-as-errors` es un modo aparte de diagnóstico completo: ignora `config.json` y pasa una copia del notebook con un corpus sintético por cada componente (un PDF con reparación de fuentes y una página escaneada para el OCR, cada formato de entrada y una URL de un servidor local, análisis de sentimiento, islandés, omorfi). Registra cada advertencia, incluidas las emitidas en código que captura excepciones, y las imprime todas bajo el encabezado de la celda, con las palabras de la biblioteca y el lugar donde se emitieron. Las advertencias conocidas e inofensivas (`diagnostyka.ZNANE_OSTRZEZENIA`) reciben una línea aparte y no cuentan. El modo necesita todas las dependencias opcionales de `requirements.txt` y el modelo `fi_core_news_lg`, y un componente que no carga lo detiene con un mensaje. El notebook y `export_results/` no se tocan, y el informe y los pasos posteriores no se ejecutan; código de salida 4 = advertencias nuevas, 0 = ninguna. El registrador cubre el módulo `warnings` en el proceso del notebook: los mensajes enviados por `logging` (por ejemplo, por `transformers`) y las advertencias de procesos hijos quedan fuera. Cuando una biblioteca sustituye el registrador (por ejemplo `logging.captureWarnings`), el modo termina con el código 1 en lugar de un falso «limpio»; lo mismo ocurre con Ctrl+C, tras imprimir las advertencias recogidas hasta entonces. Ejecútalo después de actualizar las bibliotecas.

### 1. Notebook (obligatorio)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
# Sin interfaz (CI): celdas 0-39 con nbclient, saltando la celda interactiva cell_qa_rag
python -c "import nbformat as f; from nbclient import NotebookClient as C; nb=f.read('accessible_text_analyst.ipynb',4); c=C(nb,timeout=None); c.create_kernel_manager(); c.start_new_kernel(); c.start_new_kernel_client(); [c.execute_cell(x,i) for i,x in enumerate(nb.cells[:40])]; f.write(nb,'accessible_text_analyst.ipynb'); c.km.shutdown_kernel(now=True)"
```

Es un pipeline secuencial con estado global compartido. **No reordenes las celdas ni las ejecutes fuera de orden.** El notebook escribe `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` y `theses.txt`.

### 2. Informes HTML (recomendado)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` lee las salidas de las celdas directamente del archivo `.ipynb`, así que el informe HTML debe generarse a partir de un notebook **recién ejecutado**. `requirements.txt` incluye `nbstripout` — si está activado en la configuración local de git, las salidas del notebook se eliminan al hacer commit. Genera el informe _antes_ del commit, o desactiva nbstripout en tu flujo de trabajo.

**Comprobación de la fuente.** Antes de escribir nada, `generate_report.py` comprueba que las salidas del notebook pertenecen al `source_file` de la configuración, y si no, lo rechaza (código de salida 3, no se escribe nada). Tres comprobaciones: la ruta de la fuente y la carpeta de exportación que imprimió el notebook deben coincidir con la configuración, y la ejecución guardada debe haber llegado al final de la celda de exportación; `paragraphs.csv` y `sentences.csv` no deben ser más recientes que el `.ipynb` (si no, las salidas de la última ejecución nunca se guardaron — algo típico al ejecutar el notebook en VS Code sin guardarlo); y los comienzos de página que imprimió el notebook deben aparecer en el archivo de origen (comparados como una secuencia de letras, de modo que no importan los guiones de corte unidos, los números de página eliminados ni los titulillos). Cuando el contenido no se puede comparar — escaneos leídos por OCR, imágenes, URL, una capa de texto PDF corrupta — deciden las dos primeras comprobaciones y la consola lo indica. El informe registra además si omorfi participó en la ejecución (`<meta name="ata-omorfi">`); el Libro de lo No Dicho lo lee.

Para una vista de **diagnóstico** completa y estructurada, construida directamente a partir de las exportaciones CSV/JSON:

```bash
python generate_diagnostic.py
# → export_results/<project>/diagnostic_report.html
```

`generate_diagnostic.py` solo lee los CSV/JSON exportados, así que — a diferencia de `generate_report.py` — no necesita un notebook recién ejecutado, solo las exportaciones que escribió el notebook. El resultado es un documento navegable (índice, encabezados, listas) con los temas, las tesis, las entidades agrupadas por tipo y las palabras clave principales.

### 3. Markdown para Gemini Notebook (opcional)

```bash
python generate_md.py
# → export_results/<project>/gemini_notebook_report.md
```

Esto convierte el informe HTML en un archivo Markdown sin los spans de accesibilidad (Gemini Notebook — antes NotebookLM — no aprovecha `<span lang="…">`). Ejecútalo solo si quieres cargar el informe en Gemini Notebook.

### 4. Posprocesador chamánico sin LLM (opcional)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
#                                          /emotional_undertow.txt   # solo si existe sentiment.csv
```

Genera artefactos de texto rituales directamente a partir de las exportaciones CSV/JSON del notebook — sin llamadas a LLM, sin red. Todos los textos proceden de `shamanic_locale.py` y están totalmente localizados en los nueve idiomas admitidos. Cuando existe el `sentiment.csv` opcional, produce además `emotional_undertow.txt` — una «marea emocional» por párrafo y un balance; sin él, ese único ritual simplemente se omite.

### 5. Posprocesador chamánico con LLM (opcional, requiere una clave de API de LLM)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Requiere la clave del proveedor elegido (`llm_provider`, por defecto `openai`). Crea `golden_key.env` en la raíz del proyecto con la clave que necesites:

```
OPENAI_API_KEY=sk-...          # llm_provider: openai (por defecto)
OPENROUTER_API_KEY=sk-or-...   # llm_provider: openrouter
LLM_COMPAT_API_KEY=...         # llm_provider: openai_compat (llm_base_url)
```

`golden_key.env` coincide con `*.env` en `.gitignore`, así que no se incluirá en ningún commit. Las cuatro voces se ejecutan en secuencia:

1. **Katla** transmuta la lista de entidades (`entities.csv`) en un monólogo de espíritus helados del Norte.
2. **Vieno** canta sobre la lista de palabras clave y temas. Por defecto entreteje cinco frases crudas del corpus como ecos de otra dimensión; cuando existe el `sentiment.csv` opcional, en su lugar lee el arco emocional del texto (los estados de ánimo por párrafo, condensados para caber en el límite de tokens del modelo en corpus largos) y deja que dé forma a la dinámica del canto.
3. **Lumi** lee `prophecies.txt` (obligatorio) más el monólogo de Katla y el canto de Vieno (ornamento opcional) y redacta el despacho final. Unos textos de reserva localizados cubren el caso en que falten Katla o Vieno.
4. **Sami** lee el informe de Lumi y entrega una síntesis llena de energía con la chispa de la esperanza o una llamada a la acción.

### 6. Despachador de audio chamánico (opcional, requiere ElevenLabs)

```bash
python shamanic_voice.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.mp3
#                                          /vieno_echoes_chant.mp3
#                                          /lumi_final_report.mp3
#                                          /sami_energetic_spark.mp3
```

Un script independiente de una sola ejecución que lee los cuatro artefactos narrativos producidos por `shamanic_ai.py` y sintetiza cada uno en un `.mp3` mediante el modelo `eleven_multilingual_v2` de ElevenLabs (que detecta por sí solo el idioma hablado, así que no se pasa ningún parámetro de idioma). Registra en la consola cada éxito o fallo y termina — no hay bot, ni servidor, ni sesión interactiva. Necesita dos cosas:

- `ELEVENLABS_API_KEY` en `golden_key.env` (el mismo archivo que contiene las claves de LLM).
- una asignación `voices` en `config.json` / `config.ini` que dé un ID de voz de ElevenLabs a cada una de `katla`, `vieno`, `lumi`, `sami`. Una voz con ID vacío o cuyo artefacto falte se omite (ejecuta antes `shamanic_ai.py`); el fallo de una voz no interrumpe las demás.

> **Privacidad y coste.** Igual que `shamanic_ai.py` con OpenAI, este script envía el texto de los artefactos a un servicio de terceros (ElevenLabs) para la síntesis, y ElevenLabs es una API **de pago**. El contenido sale de tu equipo — no lo ejecutes sobre material que no puedas compartir fuera.

### 7. El Libro de lo No Dicho (opcional, solo finlandés, asistido por un agente)

```bash
python ksiega_niedomowien.py scan              # qué carpetas de export_results/ son aptas
python ksiega_niedomowien.py scan --blocks     # además bloques hechos / abiertos / restantes (lento; automático con --folder)
python ksiega_niedomowien.py status            # progreso por carpeta: entradas, bloques obvios, paquetes abiertos
python ksiega_niedomowien.py tidy              # entradas sustituidas por una más reciente del mismo bloque (vista previa; --apply limpia)
python ksiega_niedomowien.py prepare --folder <name> --limit 3
#   → export_results/_kirja_tyotila/<id>/packet.json
python ksiega_niedomowien.py draft <id>        # opcional: borrador por API + seal, hasta 2 reintentos
python ksiega_niedomowien.py seal <id>         # valida draft.json, escribe blind.json
python ksiega_niedomowien.py fill <id>         # opcional: intentos a ciegas por API, después judge
python ksiega_niedomowien.py judge <id>        # → export_results/Sanomattomien_kirja.md
# <id> = el id del paquete que imprime prepare, el comienzo del nombre de la carpeta o la ruta de la carpeta del paquete
```

Un juego construido sobre `raw_roots_chant.txt`. Para cada bloque de 3 a 6 raíces consecutivas, un LLM escribe una entrada brumosa de diario en finlandés con huecos cuyas respuestas son fragmentos literales del texto de origen — deben aparecer en **ambos** archivos, `accessible_text.html` y `accessible_text.docx`, las dos versiones de la fuente de verdad. Después, un modelo ciego aparte intenta rellenar los huecos solo a partir de la entrada; cada hueco que acierta cuenta como obvio y su fragmento se elimina. Lo que queda — KATLA (el sistema de alerta) leyendo las raíces y VIENO (la narradora chamánica) con los huecos no dichos — se añade a `export_results/Sanomattomien_kirja.md`. La clave de respuestas va a `Sanomattomien_kirja.avain.json` y el estado a `Sanomattomien_kirja.tila.json`; volver a ejecutarlo nunca duplica entradas.

El script es la mitad determinista (filtros, bloques, fuente de verdad, validación, evaluación, el Libro). La mitad creativa — escribir `draft.json` — la hace o bien un agente que sigue `skills/ksiega-niedomowien/SKILL.md`, o bien un modelo por API mediante `draft`.

**Filtros de entrada.** Solo son aptas las subcarpetas de `export_results/` con nombre finlandés, `<html lang="fi">`, un canto finlandés y sin fuga gramatical; todo lo demás se rechaza con un motivo. La línea `roots.header` se elimina cuando existe. La comprobación de *fuga gramatical* detecta los corpus procesados antes de que se activara omorfi (v1.5.0): sobre todo `keywords_tfidf.csv` cuenta las formas flexionadas que sobrevivieron a la lematización más los lemas basura de spaCy, y rechaza la carpeta por encima de 1,0 por cada 100 términos. Requiere omorfi (paso 5 de la instalación). Cuando la carpeta tiene un `analysis_report.html` actual, el rechazo por fuga gramatical dice lo que sabe el informe: omorfi participó en la ejecución (entonces puede que haya que corregir el propio motor — la corrección de lemas finlandeses del notebook; notifica los ejemplos), omorfi faltaba (instálalo y vuelve a ejecutar el notebook) o la ejecución no tuvo ningún paso de omorfi. Sin un informe actual, dice que se desconoce.

**Por qué solo el finlandés.** El juego vive de lo que la lematización deja sin decir, así que solo tiene sentido allí donde reducir una palabra a su lema le quita un significado real. El finlandés es aglutinante: lo que el polaco o el ruso expresan en parte con preposiciones aparte, y el inglés sobre todo con el orden de las palabras y las palabras funcionales, el finlandés lo mete en la propia palabra — quince casos (`talossa` «en la casa», `talosta` «desde dentro de la casa», `taloon` «a la casa (adentro)», `talolle` «hacia la casa», `talotta` «sin casa»), sufijos posesivos (`taloni` «mi casa», `talonsa` «su casa»), clíticos (`-ko` pregunta, `-kin` «también», `-han` énfasis) y formas verbales que llevan a la vez persona, tiempo, modo y pasiva (`tehtäisiinkö` «¿se haría?»). El canto reduce todo eso a `TALO` y `TEHDÄ`: quién, dónde, desde dónde, hacia dónde, de quién y si acaso — todo desaparece, justo los huecos que tiene que rellenar quien escucha. En polaco y en ruso el lema pierde la desinencia, pero buena parte de la relación está en una palabra aparte (la preposición), así que el lema nunca la llevaba solo; el inglés pierde poco más allá del número y el tiempo. El islandés (cuatro casos, en gran parte regidos por preposiciones) y el italiano (preposiciones y artículos, poca flexión nominal) se acercan más al patrón polaco/ruso y al inglés, respectivamente. Técnicamente, la herramienta necesita además un analizador de diccionario para demostrar que un canto está libre de gramática y para volver a casar las raíces con el texto flexionado; en este pipeline solo el finlandés tiene uno (omorfi), y los umbrales se calibraron con corpus finlandeses reales.

**Redactor por API (`draft`).** Rebaja la barrera de entrada: no hace falta ningún agente. El script envía el paquete (el canto, las raíces y las frases de origen de `truth.sentences`) al proveedor configurado, escribe `draft.json` y lo sella; cuando `seal` rechaza el borrador, el modelo lo recibe de vuelta junto con las objeciones concretas del validador, hasta 2 reintentos (3 intentos). Los códigos de salida coinciden con los de `seal` (0 sellado, 4 sigue rechazado — corrige el último `draft.json` a mano o con la skill). Un `draft.json` existente nunca se sobrescribe sin `--force`. La skill sigue siendo el modo más potente: reintentos ilimitados, con el agente leyendo las objeciones sobre la marcha. Hay una regla que no se puede validar de forma determinista en ninguno de los dos modos: *no atribuyas a personas reales hechos o acusaciones que no estén en las frases de origen*. El prompt del redactor y la skill la enuncian, pero nada la comprueba — lee las entradas sobre personas reales antes de compartirlas.

**Rellenador ciego (`fill`).** Envía solo `blind.json` — nunca las respuestas ni la fuente — al proveedor configurado, guarda `guesses.json` y ejecuta `judge` enseguida. Proveedor: `kirja_llm_provider` (vacío = `llm_provider`); modelo: `kirja_filler_model`; `--provider` / `--model` sustituyen a ambos. `judge` por sí solo está pensado para los intentos de un subagente ciego. Tanto `draft` como `fill` piden primero un esquema JSON (salidas estructuradas); cuando el endpoint lo rechaza recurren al modo JSON simple y después al prompt solo. `fill` reintenta dos veces cuando la respuesta no sirve o le falta un hueco. Cada respuesta inservible se guarda en la carpeta del paquete (`draft_reply_N.txt` / `fill_reply_N.txt`, con `finish_reason` y la negativa, si la hay), y la consola dice dónde.

**Conectar la skill.**

- *Claude Code:* copia `skills/ksiega-niedomowien/` a `~/.claude/skills/` (personal) o a `.claude/skills/` en tu copia del repositorio. Este repositorio tiene `.claude/` en .gitignore; por eso la skill se distribuye en `skills/`.
- *Aplicaciones de Claude:* comprime la carpeta `ksiega-niedomowien/` en un ZIP (la propia carpeta debe ser la raíz del archivo) y añádela en **Customize → Skills**; la ejecución de código debe estar activada y la sesión necesita acceso a tu copia del repositorio, porque los autómatas de omorfi y `export_results/` están en tu disco. Usa la pestaña **Code** con una sesión **local**: en el modo de chat simple o en una sesión en la nube, los archivos que lee el agente — fragmentos de la fuente incluidos — se copian a un entorno en la nube.
- *Otros agentes:* `SKILL.md` es un procedimiento en Markdown sencillo con front matter YAML; cualquier agente que pueda ejecutar comandos locales en el repositorio puede seguirlo. Si no puede lanzar un subagente independiente, usa `fill` para el paso ciego.
- Un asistente solo de chat sin ejecución de comandos locales (p. ej. un GPT personalizado) no puede ejecutarlo: omorfi y sus ~130 MB de autómatas tienen que funcionar junto a tus datos.

> **Privacidad y coste.** Tres niveles, de menos a más datos: `fill` envía solo el texto brumoso de la entrada (no la fuente); `draft` envía frases literales de la fuente (`truth.sentences`) e imprime cuántas antes de la llamada; un agente que sigue la skill lee fragmentos de la fuente y los envía a su propio proveedor de modelos — y, en una sesión en la nube, trabaja sobre una copia en la nube de los archivos. Todas las llamadas a la API son de pago. Úsalas solo con material que puedas compartir con esos proveedores.

### 8. Helsinki Reacts (opcional, requiere una clave de API de LLM)

```bash
python helsinki_reacts.py <project> [<project> …]
# → export_results/_streams/<project>.md
python helsinki_reacts.py notes.txt             # también sirve cualquier archivo de texto
python helsinki_reacts.py <project> --dry-run   # muestra lo que se enviaría, sin enviar nada
python helsinki_reacts.py <project> --lang en   # idioma del directo para esta ejecución
python helsinki_reacts.py <project> --kirja     # añade la entrada de la carpeta en el Libro de lo No Dicho
```

Guion satírico de un directo: Valtteri, un streamer de Helsinki, reacciona con su chat a una grabación, y Lumi, una fría voz sintética, lee las donaciones. La entrada es el nombre de una carpeta de `export_results/` (el texto de su `accessible_text.html` sin marcado ni títulos) o cualquier archivo de texto; el guion se escribe en `export_results/_streams/<nombre>.md`, y una nueva ejecución con el mismo nombre añade `_2`, `_3`.

**El prompt es tuyo.** El prompt de sistema no está en el código: el predeterminado, `helsinki_reacts.example.md`, es deliberadamente escueto. Cópialo a `helsinki_reacts.md` (está en `.gitignore` y se usa automáticamente cuando existe) y cambia lo que quieras, o indica cualquier archivo con `--prompt`. Una regla de más o de menos cambia mucho el directo, así que compara varias ejecuciones antes de quedarte con una versión. El script solo añade lo que debe funcionar diga lo que diga el prompt: la grabación, el idioma de salida y —con `--kirja`— el bloque del Libro de lo No Dicho.

**Idioma.** `--lang`, después `reacts_lang` del config y después `ui_lang`. El finés da el propio directo, en finés corriente; cualquier otro idioma da su traducción, en la que las interjecciones finesas breves quedan sin traducir.

**El Libro de lo No Dicho (`--kirja`).** Para una carpeta con una entrada en `Sanomattomien_kirja.md`, el chat recibe el texto brumoso de la entrada y los intentos fallidos del rellenador ciego como teorías para discutir. La clave de respuestas nunca llega al modelo, y una regla fija impide que Valtteri compare un hueco con la grabación, porque los huecos esconden palabras de esa misma grabación. Sin entrada, el directo se hace sin el Libro.

Proveedor y modelo: `reacts_llm_provider` / `reacts_model` (vacíos = `llm_provider` / `llm_model`), sustituidos por `--provider` / `--model`. Esfuerzo de razonamiento: `medium` donde el razonamiento vuelve legible (Claude por OpenRouter) y `low` en los demás casos; lo sustituye `--effort low|medium|high`. Todas las entradas se leen antes de la primera llamada, así que un archivo vacío o que no esté en UTF-8 detiene la ejecución sin coste. Una respuesta más corta que `--min-chars` (1500) se descarta como negativa y se conserva en `_streams/<nombre>.rejected.md`.

> **Privacidad y coste.** Todo el texto de cada grabación va al proveedor configurado, que es una API de pago; el script lo avisa antes de la primera llamada. El resultado es una sátira sobre el material escrita por IA: léela antes de compartirla, sobre todo si nombra a personas reales; nada comprueba lo que el modelo les atribuye.

## Salida

Cada corpus analizado recibe su propio subdirectorio en `export_results/`, con el nombre del archivo de origen (sin ruta ni extensión) o un `domain_slug` en el caso de las URL. El corpus de ejemplo integrado usa `export_results/_default/`.

Cada subdirectorio contiene:

| Archivo                         | Lo produce  | Descripción                                              |
|---------------------------------|-------------|----------------------------------------------------------|
| `sentences.csv`                 | notebook    | cada frase con su índice y su idioma (`lang`)            |
| `paragraphs.csv`                | notebook    | párrafos (de 3 a 6 frases cada uno)                      |
| `theses.csv`, `theses.txt`      | notebook    | una tesis por párrafo (la frase con mayor TF-IDF); el nombre del archivo `.txt` sigue el idioma del corpus (p. ej. `tezy.txt` para el polaco, `тезисы.txt` para el ruso, `tesis.txt` para el español) |
| `keywords_tfidf.csv`            | notebook    | palabras clave (uni/bi/trigramas) con sus pesos TF-IDF   |
| `paragraphs_with_topics.csv`    | notebook    | párrafos con el tema de KMeans asignado                  |
| `topic_keywords.json`           | notebook    | palabras clave por tema                                  |
| `entities.csv`                  | notebook    | todas las entidades nombradas y sus etiquetas            |
| `language_spans.csv`            | notebook    | segmentos en otro idioma: documento, posiciones de caracteres, idioma, `block` o `inline`, texto |
| `sentiment.csv`                 | notebook *(opcional)* | sentimiento por párrafo (`para_id`, `label`, `score`, `lang`) — solo cuando `enable_sentiment` vale `true`; alimento para la capa chamánica, nunca se muestra al usuario |
| `accessible_text.html`          | notebook    | `lang` en cada párrafo más `<span lang>` en cada frase extranjera y cada segmento extranjero insertado (cita, nombre) — los lectores de pantalla cambian de voz automáticamente en cada fragmento |
| `accessible_text.docx`          | notebook    | el mismo contenido con `<w:lang>` en cada `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`, `de-DE`, `es-ES`, `fr-FR`) — Word y SAPI lo usan sin conexión, sin detector en línea |
| `analysis_report.html`           | `generate_report.py` | informe HTML global accesible                  |
| `diagnostic_report.html`         | `generate_diagnostic.py` | informe de diagnóstico estructurado (temas, tesis, entidades por tipo, palabras clave) a partir de las exportaciones CSV/JSON |
| `gemini_notebook_report.md` | `generate_md.py`     | Markdown listo para Gemini Notebook (antes NotebookLM) |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | artefactos de texto rituales / narrativos |
| `audio_scripts/*.mp3`           | `shamanic_voice.py` *(opcional)* | las cuatro voces narrativas sintetizadas en audio con ElevenLabs |

## Accesibilidad

Es el valor central del proyecto. Todo lo que sigue es intencionado y debe conservarse cuando se modifique el pipeline:

- **Sin colores ANSI, emoji ni pseudográficos en la salida.** Un lector de pantalla lee cada carácter literalmente — `[OK]` en lugar de «🟢», `---` en lugar de «───━━━».
- **Barras de progreso silenciadas** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` silencia las barras de carga y las advertencias de Hugging Face/torch antes de descargar IceBERT e icelandic-ner-bert para el islandés; `cell_corpus._silence_ocr_progress()` hace lo mismo con los motores de OCR.
- **Etiquetado `lang` por párrafo, por frase y por segmento en la exportación.** `accessible_text.html` y `accessible_text.docx` llevan un código ISO 639-1 en cada párrafo, en cada frase extranjera y en cada segmento extranjero insertado (una cita o un nombre dentro de una frase). NVDA, JAWS, Narrador, VoiceOver, Word y SAPI respetan esas etiquetas y cambian de voz automáticamente — incluso sin conexión.
- **Etiquetado fijo en inglés en el informe HTML.** `generate_report.py` envuelve siempre los fragmentos técnicos en inglés — etiquetas POS (`NOUN`, `VERB`, `ADJ`), etiquetas NER (`PER`, `ORG`, `[orgName]`), identificadores de modelos de spaCy / Hugging Face, nombres de archivo ASCII, bloques de código — en `<span lang="en">`, de modo que ya no se pronuncian con la voz rusa predeterminada del documento.
- **Etiquetado por fragmento del corpus extranjero en el HTML.** Cuando el corpus no es ruso, las salidas estructuradas (extractos de frases, listas de palabras clave, palabras de los temas, filas de clasificación RAG, tablas de lematización) se envuelven en `<span lang="target_lang">`.
- **Estructura HTML lineal** (`<main>`, jerarquía correcta de encabezados).

### Leer la salida sin saber ruso

La narración del notebook y la salida `print()` de la mayoría de las celdas están escritas en ruso. Dos características de la interfaz de Jupyter lo hacen hostil para los usuarios de lectores de pantalla que no saben ruso, y el pipeline incluye soluciones concretas para cada una:

- **Jupyter en el navegador fija `lang="en"` en el documento**, y la pregunta «¿Traducir esta página?» nunca aparece en páginas `localhost`. Por eso un notebook narrado en ruso se anuncia con una voz TTS inglesa — un caos total. La solución práctica es la **extensión de Jupyter para VS Code**: su vista de lista anuncia solo las etiquetas `code cell` / `markdown cell` sin etiquetado ISO, puedes pulsar Intro para recorrer las celdas de código y ↓ para pasar las de markdown sin escuchar su contenido, y el problema del inglés fijo queda confinado a la vista de salida (`Ctrl+Shift+↓`) — en la que puedes decidir no entrar.
- **`generate_report.py` es en la práctica obligatorio para quien no lee ruso.** Produce `analysis_report.html` con `<html lang="ru">` y el juego completo de etiquetas `<span lang="…">` por fragmento. Abierto en un navegador de verdad (no desde Jupyter), activa la pregunta «¿Traducir esta página?» para la narración rusa y, aun así, cambia la voz TTS en cada fragmento para el contenido del corpus y para los términos técnicos en inglés (POS, NER, nombres de modelos).
- **Las preguntas interactivas escriben `qa_results.html` y lo abren por ti.** `cell_qa_rag` sigue imprimiendo la consulta y las 3 mejores coincidencias en stdout — pero además escribe el mismo contenido en `export_results/<project>/qa_results.html` y llama a `webbrowser.open()` para que la página se abra en el navegador del sistema, donde funcionan tanto la traducción como el cambio de voz por fragmento. La vista de salida de Jupyter, donde el `lang="en"` fijo vuelve ilegibles para un lector de pantalla los envoltorios rusos, deja así de ser el único camino hasta el resultado. Cada consulta nueva sobrescribe el archivo.

## Limitaciones conocidas

- **El origen de los préstamos no se etiqueta.** El etiquetado de idioma (los atributos `lang`, ver *El idioma de cada palabra*) cubre las palabras que conoce el diccionario de otro idioma enumerado y los fragmentos escritos en otra escritura: letras griegas, latín dentro de un texto cirílico. Una marca de origen explícita (`греч.`, `łac.`, `z niemieckiego`, `имеет греческое происхождение`) no se enlaza con la palabra prestada, y una palabra transliterada a la escritura del texto (`фразис` en un texto ruso) conserva el idioma del corpus. Esas marcas no tienen una forma fija (abreviatura, adjetivo, una frase entera), y etiquetar como griega una `фразис` cirílica haría que el lector de pantalla cambiara a una voz griega, lo que es peor que el ruso predeterminado.
- **Finlandés: la primera palabra de la frase.** Al comienzo de una frase toda palabra va en mayúscula, y el etiquetador de spaCy toma a veces un imperativo o una interjección por un nombre propio: `Anna kuulua.` («que se oiga») se convierte en el nombre *Anna*, `Oota, miten…` («espera, cómo…») en el nombre *Oota*. La corrección de omorfi nunca anula una palabra etiquetada como nombre, porque si no los nombres reales se convertirían en palabras comunes (*Tuskia* → *tuska*, «angustia»). Una palabra así conserva su forma escrita como lema y puede aparecer en las listas de lemas, en las palabras clave y en el canto de raíces (`anna`, `oota`). Cuando el etiquetador la considera en cambio una interjección, omorfi aporta el verbo (*Oota* → `oottaa`, desde la v1.11.1). La comprobación de fuga gramatical del Libro de lo No Dicho no cuenta una palabra clave que la fuente usa también como nombre en mitad de una frase (*Anna Maria …*).
- **Nombres escritos sin sus signos diacríticos.** Un nombre extranjero solo se etiqueta cuando la propia grafía aporta la prueba: letras que el alfabeto base no tiene (`Kaczyński`), una forma que solo conoce el léxico de otro idioma de la lista, u otra escritura (`Качиньский` se etiqueta como ruso). Muchas redacciones quitan los diacríticos de los nombres extranjeros. En titulares RSS recogidos el 15 de noviembre de 2026 (Google News por país y los propios canales de los portales), los medios finlandeses escribieron *Swiatek* en 8 de 8 titulares y *Kaczynski* en 2 de 3, aunque *Wałęsa* conservó sus letras en 6 de 7; en los titulares franceses, italianos, españoles y suecos la forma sin signos predominó en al menos dos de esos tres nombres, mientras que los medios alemanes e ingleses conservaron las letras casi siempre y los rusos transliteran al cirílico. Un nombre sin signos, incluidas sus formas flexionadas (*Kaczynskin*), solo tiene letras del alfabeto base y no figura en ningún léxico con esa forma, así que se queda en el idioma base y lo lee la voz base, liste lo que liste `corpus_languages`. El texto por sí solo no lo resuelve, y ATA no adivina las letras quitadas: comparar cada palabra desconocida de letras base con léxicos extranjeros despojados de diacríticos cambiaría la voz también en palabras corrientes. Un nombre de un idioma que aquí no tiene paquete (*Erdoğan*) también se queda en el idioma base.

## Estructura del repositorio

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # pipeline principal (42 celdas)
├── generate_report.py              # generador del informe HTML (vista de lectura)
├── generate_diagnostic.py          # informe HTML de diagnóstico a partir de las exportaciones CSV/JSON
├── generate_md.py                  # conversor a Markdown para Gemini Notebook
├── shamanic_pipeline.py            # opcional: posprocesador ritual sin LLM
├── shamanic_ai.py                  # opcional: narradoras rituales basadas en LLM
├── llm_klient.py                   # selección de proveedor LLM y de clave (compartida)
├── shamanic_voice.py               # opcional: despachador de audio de ElevenLabs (una sola ejecución)
├── shamanic_locale.py              # paquete de localización de la capa chamánica
├── ksiega_niedomowien.py           # opcional: el Libro de lo No Dicho (solo finlandés)
├── helsinki_reacts.py              # opcional: guiones de directos de Helsinki Reacts (LLM)
├── helsinki_reacts.example.md      # prompt predeterminado de Helsinki Reacts (versionado)
├── helsinki_reacts.md              # tu copia de ese prompt (en .gitignore)
├── skills/ksiega-niedomowien/SKILL.md  # skill del agente para ksiega_niedomowien.py
├── config.example.json             # plantilla de configuración, extensión JSON (versionada)
├── config.example.ini              # plantilla de configuración, extensión INI (versionada)
├── config.json / config.ini        # tu configuración local (en .gitignore)
├── golden_key.env                  # claves de LLM y ElevenLabs (en .gitignore)
├── requirements.txt                # dependencias de pip
├── CLAUDE.md                       # guía para Claude Code
├── README.md                       # la versión canónica (inglés)
├── README_pl.md, README_ru.md, …   # traducciones (enlace de vuelta arriba)
├── VERSION                         # ciclo de versión en preparación (`X.Y.Z-WIP` hasta la publicación)
├── release_notes.md                # notas de versión en orden cronológico inverso
└── export_results/                 # salidas del análisis (en .gitignore)
    ├── Sanomattomien_kirja.md      # el Libro de lo No Dicho, ampliado poco a poco
    ├── _streams/                   # guiones de Helsinki Reacts
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # el nombre sigue el idioma del corpus
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── diagnostic_report.html
        ├── gemini_notebook_report.md
        └── audio_scripts/…
```

## Licencia

Publicado bajo la [MIT License](LICENSE). El pipeline se distribuye solo como código fuente — sin binarios —, y el notebook es, por naturaleza, editable celda a celda desde el navegador o desde la extensión de Jupyter para VS Code. La licencia MIT simplemente hace explícito lo que el formato ya implica.
