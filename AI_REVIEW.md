# AI-рев'ю коду: 3 view

Три view, через які проходять гроші та більшість відвідувачів:

1. [`orders.views.checkout`](#1-ordersviewscheckout): оформлення замовлення (синхронна функція);
2. [`books.views.BookListView`](#2-booksviewsbooklistview): каталог з фільтрами (клас-view);
3. [`orders.views.order_status`](#3-ordersviewsorder_status): JSON зі статусом оплати (асинхронна функція).

Рев'ю робив Claude (Claude Code) з одним і тим самим промптом для кожної view.
Кожну рекомендацію я перевірив сам. Прийняті внесено в код і покрито тестами,
а для відхилених нижче вказано причину.

## Промпт для рев'ю

```text
Ти — досвідчений Django-розробник. Зроби code review цієї view
(Django 6.1, PostgreSQL, Python 3.13). Код моделей, форм і сервісів,
які вона викликає, додано нижче.

Перевір чотири речі:
1. Коректність: помилки логіки, крайні випадки (порожні дані, неправильні
   параметри, конкурентні запити), поведінка при помилках.
2. Безпека: доступ до чужих даних, перевірка вхідних даних, HTTP-методи,
   CSRF, відкриті редиректи.
3. SQL-запити: кількість запитів (N+1), зайві запити, індекси, блокування.
4. Читабельність: назви, довжина функції, коментарі.

Для кожної проблеми дай: що не так, конкретний сценарій, коли це проявиться,
і виправлений код. Не пиши про те, що вже зроблено правильно. Якщо проблема
лише теоретична, так і скажи.
```

Позначки в таблицях: ✅ прийнято (є в коді й у тестах), ❌ відхилено (з причиною).

---

## 1. `orders.views.checkout`

### Початковий код

```python
@login_required  # anonymous -> LOGIN_URL?next=/orders/checkout/; the cart stays
def checkout(request):
    cart = Cart(request)
    if not cart:
        messages.info(request, _("Your cart is empty."))
        return redirect("cart:detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                data = form.cleaned_data
                order = create_order(
                    request.user,
                    cart.quantities(),
                    full_name=data["full_name"],
                    phone=data["phone"],
                    address=data["address"],
                )
            except OrderError as error:
                for text in error.messages:
                    messages.error(request, text)
                return redirect("cart:detail")

            cart.clear()
            if data["save_to_profile"]:
                request.user.phone = data["phone"]
                request.user.address = data["address"]
                request.user.save(update_fields=["phone", "address"])
            messages.success(request, _("%(order)s is created, ...") % {"order": order})
            return redirect(order)
    else:
        form = CheckoutForm(initial={...})  # from the profile

    return render(request, "orders/checkout.html", {"form": form})
```

### Рекомендації AI і рішення

| # | Рекомендація AI | Рішення |
|---|---|---|
| 1 | **HTTP-методи.** Будь-який метод, крім POST, іде у гілку `else`: на `PUT`, `PATCH` чи `DELETE` view відповідає сторінкою з формою і кодом 200. Потрібен `@require_http_methods(["GET", "POST"])`. | ✅ Прийнято. Метод, який view не обробляє, має отримувати 405. Решта view проєкту вже використовують `require_POST` / `require_GET`. |
| 2 | **Подвійне натискання «Оформити».** Два POST майже одночасно читають сесію ще до `cart.clear()` і створюють два замовлення. Пропозиція: одноразовий токен у формі або блокування кнопки через JavaScript. | ❌ Відхилено. Від перепродажу захищає `select_for_update` у `create_order()`: друге замовлення або теж має товар, або отримує помилку «немає в наявності». Зайве замовлення лишається неоплаченим: покупець може скасувати його сам, а менеджер скасовує такі замовлення командою `cancel_unpaid_orders`, і вона повертає книги на склад. Токен для однієї кнопки — забагато коду як для цього ДЗ. |
| 3 | **Ціна могла змінитися.** Кнопка показує «Оформити · 250 ₴», а `create_order()` бере ціну з бази в момент POST. Якщо менеджер змінив ціну між цими двома моментами, сума буде іншою. Пропозиція: передавати суму з форми й порівнювати. | ❌ Відхилено. Брати ціну з бази — правильно (у `CheckoutForm` навмисно немає `total`, щоб її не можна було підмінити). Покупець бачить фінальну суму на сторінці замовлення **до** оплати: «Оплатити» — окремий крок, і неоплачене замовлення можна скасувати. |
| 4 | **Профіль зберігається поза транзакцією.** Якщо `request.user.save()` впаде, замовлення вже створено, а покупець бачить 500. | ❌ Відхилено. Головне — замовлення, і воно вже зафіксоване (COMMIT). Помилка запису двох полів профілю — малоймовірний збій бази. Загортати їх у ту саму транзакцію означало б скасовувати замовлення через телефон у профілі. |
| 5 | **Довга функція:** винести оновлення профілю в окрему функцію. | ❌ Відхилено. Це 4 рядки з коментарем, і вони читаються на місці. Окрема функція лише додала б стрибок під час читання. |

### Фінальний код

Змінився лише заголовок функції, тіло залишилося тим самим:

```python
@login_required  # anonymous -> LOGIN_URL?next=/orders/checkout/; the cart stays
# PUT / DELETE / PATCH -> 405 (they used to get the form page with 200)
@require_http_methods(["GET", "POST"])
def checkout(request):
    ...
```

Тест: `tests/unit/test_views.py::test_checkout_accepts_only_get_and_post`
(PUT / PATCH / DELETE → 405).

---

## 2. `books.views.BookListView`

### Початковий код

```python
class BookListView(ElidedPaginationMixin, ListView):
    model = Book
    context_object_name = "books"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            super().get_queryset()
            .select_related("author")
            .prefetch_related("categories")
        )

        self.filter_form = BookFilterForm(self.request.GET or None)
        if not self.filter_form.is_valid():
            return queryset

        data = self.filter_form.cleaned_data
        if data["q"]:
            queryset = queryset.filter(
                Q(title__icontains=data["q"]) | Q(author__name__icontains=data["q"])
            )
        if data["category"]:
            queryset = queryset.filter(categories=data["category"])
        if data["author"]:
            queryset = queryset.filter(author=data["author"])
        queryset = queryset.by_stock_status(data["stock"])
        if data["price_min"] is not None:
            queryset = queryset.filter(price__gte=data["price_min"])
        if data["price_max"] is not None:
            queryset = queryset.filter(price__lte=data["price_max"])
        if data["sort"]:
            # "pk" as a tie-breaker: books with equal price keep a stable order,
            # so the same book doesn't jump between pages
            queryset = queryset.order_by(data["sort"], "pk")
        return queryset
```

### Рекомендації AI і рішення

| # | Рекомендація AI | Рішення |
|---|---|---|
| 1 | **Один неправильний параметр скидає всі фільтри.** `?q=kobzar&category=deleted` (старе посилання на видалену категорію): форма невалідна, і view повертає **весь каталог** без пошуку. Після `is_valid()` у `cleaned_data` лишаються поля, які пройшли перевірку, тож їх можна застосувати й без невалідних. | ✅ Прийнято. Помилка біля поля показується як і раніше, але пошук та інші фільтри тепер працюють. |
| 2 | **Конфлікт цін** («від 500 до 100»): `clean()` додає помилку форми, але обидві ціни лишаються в `cleaned_data`. Після зміни №1 фільтр «від 500 до 100» завжди давав би порожній список. | ✅ Прийнято. У `BookFilterForm.clean()` обидві ціни прибираються з `cleaned_data` перед помилкою, тому каталог ігнорує тільки ціни. |
| 3 | **Нестабільний порядок за замовчуванням.** Коментар у коді каже, що `pk` потрібен, щоб книжка не «стрибала» між сторінками, але без `?sort=` діє `Book.Meta.ordering = ["title"]`, тобто без `pk`. Дві книжки з однаковою назвою (різні видання) PostgreSQL може віддати в різному порядку на сторінках 1 і 2. | ✅ Прийнято. Тепер завжди `order_by(sort or "title", "pk")`. |
| 4 | **`self.filter_form` присвоюється в `get_queryset()`**, а не в `__init__` / `setup()`. Якщо `get_context_data()` викличуть без `get_queryset()`, буде `AttributeError`. | ❌ Відхилено. `ListView.get()` завжди викликає `get_queryset()` перед `get_context_data()`. Форма і queryset будуються з тих самих `GET`-даних, тому тримати їх разом зрозуміліше. |
| 5 | **`icontains` = повний перегляд таблиці** (`ILIKE '%...%'` не використовує звичайний індекс). Пропозиція: GIN-індекс `pg_trgm` або повнотекстовий пошук PostgreSQL. | ❌ Відхилено. У каталозі сотні книжок, а не мільйони, тож перегляд таблиці займає мілісекунди. `pg_trgm` потребує розширення PostgreSQL і міграції. Повернемося до цього, коли каталог виросте. |
| 6 | **Фільтр за `ManyToMany` (`categories=`) може дублювати книжки.** | ❌ Перевірено, проблеми немає: фільтр за **однією** категорією, а книжка має кожну категорію не більше одного разу. Дублі з'явилися б лише при кількох категоріях (`categories__in`), а форма дозволяє вибрати одну. |

### Фінальний код

```python
    def get_queryset(self):
        queryset = (
            super().get_queryset()
            .select_related("author")
            .prefetch_related("categories")
        )

        # Unbound form (None) when there are no GET params -> no validation errors
        self.filter_form = BookFilterForm(self.request.GET or None)
        # After is_valid() cleaned_data holds only the fields that passed:
        # one wrong parameter (an old link to a deleted category) shows its
        # error, and the other filters (?q=...) still work, instead of the
        # whole catalog without any filter
        self.filter_form.is_valid()
        data = getattr(self.filter_form, "cleaned_data", {})  # unbound: none

        if data.get("q"):
            queryset = queryset.filter(
                Q(title__icontains=data["q"]) | Q(author__name__icontains=data["q"])
            )
        if data.get("category"):
            queryset = queryset.filter(categories=data["category"])
        if data.get("author"):
            queryset = queryset.filter(author=data["author"])
        queryset = queryset.by_stock_status(data.get("stock"))
        if data.get("price_min") is not None:
            queryset = queryset.filter(price__gte=data["price_min"])
        if data.get("price_max") is not None:
            queryset = queryset.filter(price__lte=data["price_max"])
        # Always with "pk" as a tie-breaker, the default sort (Book.Meta.ordering
        # = title) too: books with an equal title or price keep a stable order,
        # so the same book doesn't jump between pages
        return queryset.order_by(data.get("sort") or "title", "pk")
```

`books/forms.py`, `BookFilterForm.clean()`:

```python
        if price_min is not None and price_max is not None and price_min > price_max:
            # Out of cleaned_data: the catalog ignores both prices (instead of
            # "from 500 to 100" = always empty) and applies the other filters
            del cleaned_data["price_min"], cleaned_data["price_max"]
            raise forms.ValidationError(_("“Price from” can't be greater than “Price to”."))
```

Тести в `tests/unit/test_views.py`:
- `test_book_list_wrong_parameter_keeps_the_other_filters`: невідома категорія + пошук;
- `test_book_list_price_from_greater_than_to_ignores_only_prices`: конфлікт цін + пошук;
- `test_book_list_order_always_ends_with_pk`: `pk` в кінці сортування, і за замовчуванням, і з `?sort=`.

---

## 3. `orders.views.order_status`

### Початковий код

```python
@never_cache
@require_GET
async def order_status(request, pk):
    from payments.models import Payment

    user = await request.auser()
    if not user.is_authenticated:
        return JsonResponse({"error": "login required"}, status=401)

    order = await (
        Order.objects.filter(pk=pk, user=user)
        .values("pk", "status", "payment_status", "total")
        .afirst()
    )
    if order is None:
        return JsonResponse({"error": "not found"}, status=404)

    paid = await Payment.objects.filter(
        order_id=pk, status=Payment.Status.SUCCEEDED
    ).aaggregate(total=Sum("amount"))
    paid_amount = paid["total"] or Decimal("0.00")
    amount_due = max(order["total"] - paid_amount, Decimal("0.00"))

    return JsonResponse({...})  # id, statuses + labels, paid_amount, amount_due
```

### Рекомендації AI і рішення

| # | Рекомендація AI | Рішення |
|---|---|---|
| 1 | **Два запити замість одного.** Замовлення і сума платежів читаються окремо. Сторінку оплати опитують кожні кілька секунд, і кожне опитування — це 2 звернення до бази з потоку `sync_to_async`. Суму можна отримати в тому самому запиті: `annotate(paid=Sum("payments__amount", filter=Q(payments__status=SUCCEEDED)))`, тобто `LEFT JOIN` + `SUM ... FILTER (WHERE ...)` + `GROUP BY`. | ✅ Прийнято. Один запит замість двох для замовлення і платежів. SQL перевірено: `SUM("payments_payment"."amount") FILTER (WHERE status = 'succeeded') ... LEFT OUTER JOIN ... GROUP BY 1`. |
| 2 | **Дублювання логіки** `Order.paid_amount` / `amount_due`: краще викликати властивості моделі. | ❌ Відхилено. Ці властивості синхронні (`aggregate()` всередині), і в async view вони дали б `SynchronousOnlyOperation`. Повторюється лише один рядок `max(total - paid, 0)`, а async-версія властивостей у моделі — це більше коду, ніж цей рядок. |
| 3 | **`Order.Status(order["status"])` впаде з `ValueError`,** якщо в базі опиниться невідоме значення. | ❌ Відхилено. Значення записує лише код через `TextChoices`. Невідоме значення в базі — це помилка даних, і 500 з трасуванням у логах тут корисніший, ніж мовчазний обхід. |
| 4 | **Обмеження частоти запитів (rate limiting)** для ендпоінта, який опитують. | ❌ Відхилено для цього ДЗ. Обмеження частоти логічно робити на рівні nginx, а він — окрема відкладена задача. Опитування й так обмежене: `static/js/payment_status.js` зупиняється, щойно отримає результат, або після 30 спроб (близько хвилини). |
| 5 | **Чи працюють `@never_cache` і `@require_GET` з async-функцією?** | ❌ Змін не потрібно: з Django 5.0 обидва декоратори підтримують async view. Тест `test_order_status_json` перевіряє заголовок `Cache-Control`, а `test_health_accepts_only_get` — 405. |

### Фінальний код

```python
    user = await request.auser()
    if not user.is_authenticated:
        return JsonResponse({"error": "login required"}, status=401)

    # One SQL query: the order and the sum of its succeeded payments
    # (LEFT JOIN payments + GROUP BY order + SUM ... FILTER (WHERE ...)).
    # user=user: someone else's order looks the same as a missing one.
    order = await (
        Order.objects.filter(pk=pk, user=user)
        .annotate(
            paid=Sum(
                "payments__amount",
                filter=Q(payments__status=Payment.Status.SUCCEEDED),
            )
        )
        .values("pk", "status", "payment_status", "total", "paid")
        .afirst()
    )
    if order is None:
        return JsonResponse({"error": "not found"}, status=404)

    # SUM over no rows is NULL in SQL -> None in Python
    paid_amount = order["paid"] or Decimal("0.00")
    amount_due = max(order["total"] - paid_amount, Decimal("0.00"))
```

Тести в `tests/unit/test_async_views.py`:
- наявний `test_order_status_json` (успішний платіж 100 + платіж 200 в очікуванні → оплачено 100, до сплати 200): тепер він перевіряє `filter=Q(...)`;
- новий `test_order_status_without_payments_is_zero_paid`: без платежів `SUM` повертає `NULL`, у відповіді `0,00`.

---

## Підсумок

| View | Рекомендацій | Прийнято | Відхилено |
|---|---|---|---|
| `checkout` | 5 | 1 | 4 |
| `BookListView` | 6 | 3 | 3 |
| `order_status` | 5 | 1 | 4 |

Найкорисніші рекомендації — ті, де AI порівнював код із його ж коментарями та
з поведінкою в крайніх випадках: невалідний параметр скидав усі фільтри, а `pk`
був лише в одній гілці сортування. Більшість відхилених — теоретичні проблеми,
від яких проєкт уже захищений в іншому місці (блокування в `create_order`,
команда `cancel_unpaid_orders`, ціни тільки з бази).
