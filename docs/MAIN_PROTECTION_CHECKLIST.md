# УКР-07: як забезпечити захист `main`

**Стан перевірки 31.10.2026:** `GET /repos/juv4uk/ukrainian-books/branches/main` повідомив `protected: false`; `GET /repos/juv4uk/ukrainian-books/rulesets` повернув `[]`. Детальний endpoint `branches/main/protection` недоступний цьому GitHub App (403). **Гілка наразі не підтверджена захищеною.** Перед застосуванням інструкції перевірити стан повторно.

## Дві незалежні складові

1. **CI-передумови в репозиторії:** `python3 scripts/check_workflow_security.py` перевіряє наявність важливих workflow, кореневе `contents: read`, відсутність наявних записів `write` в `permissions:`, небезпечних тригерів `pull_request_target` / `workflow_run` і PR-запуск перевірки якості. Негативні сценарії — `python3 -m unittest discover -s tests -p 'test_workflow_security.py' -v`.
2. **Реальний захист на сервері GitHub:** це **не YAML-файл** і не вмикається самим CI. Потрібний активний ruleset для `main` або налаштоване branch protection, підтверджене перевіркою стану та спробою небажаної дії без її виконання.

## Дії власника репозиторію

1. У GitHub **Settings → Rules → Rulesets** створити **Active** branch ruleset, що включає саме `main`; не залишати у режимі Evaluate.
2. Увімкнути **Require a pull request before merging** та **мінімум 1 approval від іншого рецензента з належними правами**. Додатково вимагати dismiss stale approvals і вирішення review threads.
3. Увімкнути **Require status checks to pass** зі строгим оновленням PR відносно `main` та конкретними унікальними назвами job: `Структура, права та посилання`, `Перевірка паспортів і негативні тести`, `Нумерація, цілісність та дефект 18.95`, `Мінімальні права й безпечні тригери`. Спочатку дочекатися появи нової перевірки в Actions; обирати саме її фактичну назву й відповідне джерело GitHub Actions.
4. Увімкнути **Block force pushes**, заборону видалення `main` і без потреби не додавати винятки bypass (включно з адміністраторами, якщо доступна відповідна настройка).
5. Переконатися, що для PR з новим комітом стара approval втрачає чинність, а PR з невдалим required check не пропускається до merge.
6. Повторити незалежний аудит конфігурації на GitHub, зафіксувати дату, активні правила, required checks, кількість required reviewers і посилання в [Issue #8](https://github.com/juv4uk/ukrainian-books/issues/8). Лише тоді можна стверджувати, що `main` захищено.

## Межі автоматичної перевірки

Скрипт використовує **вузький передбачуваний піднабір YAML без зовнішнього парсера**. Нестандартний синтаксис `permissions` відхиляється, але він не перевіряє повну семантику YAML, інші ризики supply chain, поведінку дій та реальні налаштування API. Тому його зелений статус **не є доказом branch protection**. Під час суттєвого рефакторингу YAML переглянути і тести, і саму реалізацію.

**Офіційні джерела:** [GitHub: Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets); [GitHub: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches); [GitHub Actions: Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).

**Ліцензія:** цей документ і власні скрипти підпорядковуються чинній «ВОЛЬНІСТЬ» у межах прав на власні внески. `LICENSE` і `VOLNOST.md` не змінюються.
