# Покриття тестами

Звіт згенеровано командою:

```bash
pytest                                                  # тести + дані покриття у файлі .coverage
coverage report --format=markdown --precision=2         # таблиця нижче, у форматі Markdown
```

Налаштування в `.coveragerc`: рахується лише власний код (без `.venv`,
тестів, міграцій і файлів налаштувань). `pytest.ini` вимагає щонайменше 70%.

Загалом **96.75%**, 212 тестів. Моделі `books`, `orders`, `payments`:
**100%** лише від `tests/unit/test_models.py`.

Детальний звіт з підсвіченими непокритими рядками: `htmlcov/index.html`
(створюється при кожному `pytest`, у git не потрапляє).

| Name                                                 |    Stmts |     Miss |      Cover |
|----------------------------------------------------- | -------: | -------: | ---------: |
| books/\_\_init\_\_.py                                |        0 |        0 |    100.00% |
| books/admin.py                                       |       76 |       13 |     82.89% |
| books/apps.py                                        |        5 |        0 |    100.00% |
| books/forms.py                                       |       48 |        0 |    100.00% |
| books/management/\_\_init\_\_.py                     |        0 |        0 |    100.00% |
| books/management/commands/\_\_init\_\_.py            |        0 |        0 |    100.00% |
| books/management/commands/book\_stats.py             |       70 |        0 |    100.00% |
| books/management/commands/seed\_books.py             |       23 |        0 |    100.00% |
| books/models.py                                      |       78 |        0 |    100.00% |
| books/urls.py                                        |        4 |        0 |    100.00% |
| books/views.py                                       |      114 |        3 |     97.37% |
| cart/\_\_init\_\_.py                                 |        0 |        0 |    100.00% |
| cart/apps.py                                         |        5 |        0 |    100.00% |
| cart/cart.py                                         |       63 |        0 |    100.00% |
| cart/context\_processors.py                          |        3 |        0 |    100.00% |
| cart/forms.py                                        |        4 |        0 |    100.00% |
| cart/urls.py                                         |        4 |        0 |    100.00% |
| cart/views.py                                        |       40 |        0 |    100.00% |
| config/\_\_init\_\_.py                               |        0 |        0 |    100.00% |
| config/i18n.py                                       |        6 |        0 |    100.00% |
| config/logging\_filters.py                           |        8 |        0 |    100.00% |
| config/middleware.py                                 |       74 |        0 |    100.00% |
| config/urls.py                                       |       11 |        3 |     72.73% |
| config/views.py                                      |       47 |        1 |     97.87% |
| orders/\_\_init\_\_.py                               |        0 |        0 |    100.00% |
| orders/admin.py                                      |      104 |       10 |     90.38% |
| orders/apps.py                                       |        5 |        0 |    100.00% |
| orders/emails.py                                     |       25 |        0 |    100.00% |
| orders/forms.py                                      |       14 |        0 |    100.00% |
| orders/management/\_\_init\_\_.py                    |        0 |        0 |    100.00% |
| orders/management/commands/\_\_init\_\_.py           |        0 |        0 |    100.00% |
| orders/management/commands/cancel\_unpaid\_orders.py |       46 |        4 |     91.30% |
| orders/models.py                                     |       79 |        0 |    100.00% |
| orders/services.py                                   |       61 |        5 |     91.80% |
| orders/urls.py                                       |        4 |        0 |    100.00% |
| orders/views.py                                      |       76 |        0 |    100.00% |
| payments/\_\_init\_\_.py                             |        0 |        0 |    100.00% |
| payments/admin.py                                    |       65 |        1 |     98.46% |
| payments/apps.py                                     |        5 |        0 |    100.00% |
| payments/emails.py                                   |        5 |        0 |    100.00% |
| payments/models.py                                   |       30 |        0 |    100.00% |
| payments/providers/\_\_init\_\_.py                   |        0 |        0 |    100.00% |
| payments/providers/base.py                           |       19 |        3 |     84.21% |
| payments/providers/manual.py                         |        4 |        0 |    100.00% |
| payments/providers/registry.py                       |       10 |        0 |    100.00% |
| payments/providers/stripe\_checkout.py               |       83 |        1 |     98.80% |
| payments/services.py                                 |      133 |        3 |     97.74% |
| payments/urls.py                                     |        4 |        0 |    100.00% |
| payments/views.py                                    |       40 |        0 |    100.00% |
| users/\_\_init\_\_.py                                |        0 |        0 |    100.00% |
| users/admin.py                                       |        8 |        0 |    100.00% |
| users/apps.py                                        |        7 |        0 |    100.00% |
| users/forms.py                                       |       22 |        0 |    100.00% |
| users/models.py                                      |       20 |        0 |    100.00% |
| users/phone.py                                       |       11 |        0 |    100.00% |
| users/signals.py                                     |       18 |        2 |     88.89% |
| users/urls.py                                        |        4 |        0 |    100.00% |
| users/views.py                                       |       78 |        5 |     93.59% |
| **TOTAL**                                            | **1663** |   **54** | **96.75%** |
