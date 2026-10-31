# РЕД-06: унікальність ключів у редакторських JSON

Python `json.loads` типово зберігає останнє значення, якщо ключ в одному JSON-об'єкті повторено. Через це конфлікт у `status`, `rights.verified`, `review.reviewer` чи `sources.*.url` може стати невидимим для валідатора після розбору.

## Межі

Новий незалежний скрипт `scripts/check_json_unique_keys.py` аналізує тільки `editorial/cards/**/*.json` та `docs/VERSE_CARD_TEMPLATE.json` і застосовує `object_pairs_hook` для перевірки унікальності ключів на кожному рівні. Однакові назви ключів в окремих об'єктах або файлах допустимі. Недійсні JSON/UTF-8 та символічні посилання відхиляються. Відсутність карток повідомляється як `checked_cards: 0` — не як наукове завершення.

## Запуск

```sh
python3 -m unittest discover -s tests -p 'test_json_unique_keys.py' -v
python3 scripts/check_json_unique_keys.py
python3 scripts/check_editorial_cards.py
python3 scripts/check_project.py
```

Окремий workflow `.github/workflows/json-unique-keys.yml` виконує власні тести та скрипт на PR, push у `main` і вручну. Тести використовують виключно синтетичні JSON-рядки.

## Чого скрипт не підтверджує

Він не засвідчує справжність санскриту, коректність перекладу, незалежність рецензії чи належність прав. Файли попереднього CLAIM РЕД-02 — `scripts/check_editorial_cards.py`, `tests/test_editorial_cards.py`, `docs/VERSE_CARD_SCHEMA.md` — залишаються незмінними. «ВОЛЬНІСТЬ» поширюється тільки на власний внесок; її текст не змінено.
