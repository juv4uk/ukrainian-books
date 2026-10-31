# Верстальна машина для PDF: XeLaTeX

**Статус:** працює. Доведена артефактом — PDF, який складає GitHub Actions і
прикріплює до прогону.

## Що це

Конвеєр із трьох ланок, який перетворює власні редакторські картки на готовий
PDF-файл, не пишучи жодного рядка книжкового тексту руками:

```
editorial/cards/*.json  →  scripts/build_pilot_book.py  →  generated/verses.tex
                                                                   ↓
                                                     XeLaTeX + makeindex
                                                                   ↓
                                                            main.pdf
```

## Ланки

| Ланка | Файл | Роль |
| --- | --- | --- |
| Генератор | `scripts/build_pilot_book.py` | читає картки, екранує LaTeX, пише `generated/*.tex` |
| Шаблон | `books/ashtavakra-hita-pilot/main.tex` | титул, вихідні дані, передмова, розділи, апарат, покажчик |
| Паспорт | `books/ashtavakra-hita-pilot/PROVENANCE.md` | 12 полів прав і походження; без нього збірка не запускається |
| Шлюз | `scripts/check_provenance.py` | блокує PDF, якщо паспорт не повний або статус не дозволяє публікацію |
| Збірка | `.github/workflows/build-books.yml` | `workflow_dispatch`, XeLaTeX, артефакт |

## Вимоги до середовища

- `xelatex` (пакет `texlive-xetex`) — рушій, який уміє системні шрифти й Unicode;
- `texlive-lang-cyrillic` — українські шаблони переносу для polyglossia;
- `texlive-latex-recommended` — `fontspec`, `polyglossia`, `xcolor`;
- `texlive-fonts-recommended` — TFM `pzdr`, без якого XeTeX-драйвер `hyperref`
  падає на `\XeTeXLinkBox`;
- `fonts-dejavu-core` — шрифт DejaVu Serif: кирилиця **і** діакритика IAST
  (`ā ī ū ṛ ṣ ṭ ḥ ṃ ñ ṅ ś`) в одному шрифті;
- `makeindex` — покажчик термінів;
- `latexmk` — багатопрохідна збірка.

Шаблон не використовує пакетів із `texlive-latex-extra`: жодного `titlesec`,
`booktabs` чи `needspace`. Це зроблено навмисно — щоб збірка не залежала від
пакета, якого немає в мінімальному образі.

`hyperref` підключається умовно:

```tex
\IfFileExists{pzdr.tfm}{\usepackage[hidelinks]{hyperref}}{}
```

Якщо TFM немає, PDF складеться без закладок, а не впаде.

## Шрифт і діакритика

DejaVu Serif покриває Latin Extended Additional, тому IAST не потребує окремого
шрифту й не дає «Missing character». Перевірка в CI: якщо `main.log` містить
`Missing character`, це помилка збірки.

## Що зверстано і з чого

Пілот збирається з власних полів карток: `ukrainian_translation`,
`literal_meaning`, `grammar`, `commentary`, `variants`. Поля `sanskrit` і `iast`
генератор **не читає** — вони відтворюють транскрипції GRETIL і SARIT з їхніми
власними умовами. Це зафіксовано в константі `WITNESS_FIELDS` і перевіряється
тестом `tests/test_pilot_book.py`.

## Локальна збірка

```sh
python3 scripts/build_pilot_book.py
cd books/ashtavakra-hita-pilot
latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex
pdfinfo main.pdf | grep Pages
```

Якщо `xelatex` не встановлений, а `xetex` є, формат можна зібрати вручну:

```sh
xetex -ini -interaction=nonstopmode -jobname=xelatex -progname=xelatex -etex xelatex.ini
```

Це створює `xelatex.fmt`; далі `xetex -fmt=xelatex main.tex`. Спосіб робочий, але
це обхід: штатний шлях — пакет `texlive-xetex`, який CI і ставить.

## Перевірки

```sh
python3 scripts/check_project.py          # структура, ліцензія, посилання
python3 scripts/check_provenance.py       # паспорт прав у books/
python3 scripts/build_pilot_book.py --check   # чи не застаріла верстка
python3 -m unittest discover -s tests -p 'test_pilot_book.py' -v
```

## Межі

- Машина верстає **лише власні поля карток**. Санскритського тексту вона не
  ставить — це рішення правове, а не технічне.
- Машина не перевіряє наукову якість перекладу й не замінює рецензії.
- Наявність PDF не означає, що книгу можна видавати. Що саме можна видати зараз
  і що блокує повну книгу — у `docs/VYDAVNYCHYI_VYSNOVOK.md`.
