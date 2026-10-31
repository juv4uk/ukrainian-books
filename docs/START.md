# Розпочати роботу в ukrainian-books

Репозиторій уже створено: [juv4uk/ukrainian-books](https://github.com/juv4uk/ukrainian-books), основна гілка — `main`.

## Місце роботи

1. Перегляньте [дорожню карту](../tasks/ROADMAP.md) та відкриті [Issues](https://github.com/juv4uk/ukrainian-books/issues).
2. Для дослідження відкрийте Issue з точними віршами, джерелами та CLAIM.
3. Створіть окрему гілку й PR; автоматична перевірка якості запуститься сама.
4. У `Actions` можна вручну запустити **«Якість і походження»** або **«Складання власних видань»**. Другий workflow повідомить про відсутність книжок, поки немає підтверджених власних TeX-джерел.
5. У `Settings → Rules → Rulesets` захистіть `main` від force-push та увімкніть PR review і обов'язкову перевірку якості, якщо функції доступні на плані.

```sh
git clone https://github.com/juv4uk/ukrainian-books.git
cd ukrainian-books
python3 scripts/check_project.py
python3 scripts/bootstrap_issues.py --dry-run
```

**Ліцензія:** [«ВОЛЬНІСТЬ»](../LICENSE) — єдина; не додавати інших ліцензій. Не імпортуйте чужі книжки з `livros` без незалежно встановленого права.
