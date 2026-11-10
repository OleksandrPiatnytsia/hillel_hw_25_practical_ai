"""Unit tests of the views: one request -> status code, redirect, context.

Whole user flows (several requests in a row) are in tests/integration/.
"""

import pytest
from django.urls import reverse
from pytest_django.asserts import assertRedirects, assertTemplateUsed

from config import views as config_views
from orders.models import Order

from ..factories import BookFactory, CategoryFactory, OrderFactory, PaymentFactory
from ..fakes import stripe_event_payload, stripe_webhook_headers
from ..helpers import message_levels

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def test_book_list_filters_by_search_and_category(client):
    poetry = CategoryFactory(name="Poetry", slug="poetry")
    BookFactory(title="Kobzar", author__name="Taras Shevchenko", categories=[poetry])
    BookFactory(title="Kobzar for kids", author__name="Someone Else")
    BookFactory(title="Zakhar Berkut", author__name="Ivan Franko")

    response = client.get(reverse("books:list"), {"q": "kobzar", "category": "poetry"})

    assert response.status_code == 200
    assertTemplateUsed(response, "books/book_list.html")
    assert [book.title for book in response.context["books"]] == ["Kobzar"]


def test_book_list_sorts_by_price(client):
    BookFactory(title="Cheap", price=50)
    BookFactory(title="Expensive", price=500)

    response = client.get(reverse("books:list"), {"sort": "-price"})

    assert [book.title for book in response.context["books"]] == ["Expensive", "Cheap"]


def test_book_list_wrong_parameter_keeps_the_other_filters(client):
    """AI review (AI_REVIEW.md, BookListView): an invalid ?category= used to
    drop ALL filters and show the whole catalog."""
    BookFactory(title="Kobzar")
    BookFactory(title="Zakhar Berkut")

    response = client.get(reverse("books:list"), {"q": "kobzar", "category": "deleted-category"})

    assert "category" in response.context["filter_form"].errors  # the error is shown
    assert [book.title for book in response.context["books"]] == ["Kobzar"]


def test_book_list_price_from_greater_than_to_ignores_only_prices(client):
    BookFactory(title="Kobzar", price=100)
    BookFactory(title="Zakhar Berkut", price=200)

    response = client.get(
        reverse("books:list"), {"q": "kobzar", "price_min": "500", "price_max": "100"}
    )

    assert response.context["filter_form"].non_field_errors()
    assert [book.title for book in response.context["books"]] == ["Kobzar"]


@pytest.mark.parametrize(
    ("params", "expected_order"),
    [({}, ("title", "pk")), ({"sort": "-price"}, ("-price", "pk"))],
)
def test_book_list_order_always_ends_with_pk(client, params, expected_order):
    """Books with an equal title / price must not jump between pages."""
    response = client.get(reverse("books:list"), params)

    assert response.context["paginator"].object_list.query.order_by == expected_order


def test_book_detail_shows_quantity_in_cart(client):
    book = BookFactory()
    client.post(reverse("cart:add", args=[book.pk]), {"quantity": 2})

    response = client.get(book.get_absolute_url())

    assert response.status_code == 200
    assert response.context["in_cart"] == 2


def test_missing_book_is_404(client):
    assert client.get(reverse("books:detail", args=[999999])).status_code == 404


@pytest.mark.parametrize(
    ("client_fixture", "expected_status"),
    [("customer_client", 403), ("manager_client", 200)],
)
def test_book_create_needs_permission(request, client_fixture, expected_status):
    # request.getfixturevalue(): a fixture chosen by name from the parameters
    client = request.getfixturevalue(client_fixture)

    assert client.get(reverse("books:create")).status_code == expected_status


def test_author_list_counts_books(client):
    book = BookFactory(author__name="Lesya Ukrainka")
    BookFactory(author=book.author)

    response = client.get(reverse("books:author_list"))

    assert response.context["authors"][0].books_count == 2


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------


def test_cart_add_accepts_only_post(client):
    book = BookFactory()

    assert client.get(reverse("cart:add", args=[book.pk])).status_code == 405


def test_cart_add_redirects_back_only_to_own_site(client):
    book = BookFactory()
    url = reverse("cart:add", args=[book.pk])

    same_site = client.post(url, {"quantity": 1, "next": "/?page=2"})
    other_site = client.post(url, {"quantity": 1, "next": "https://evil.example/"})

    assertRedirects(same_site, "/?page=2", fetch_redirect_response=False)
    assertRedirects(other_site, reverse("cart:detail"))


def test_cart_add_more_than_stock_warns(client):
    book = BookFactory(stock=2)

    response = client.post(reverse("cart:add", args=[book.pk]), {"quantity": 5})

    assert message_levels(response) == ["warning"]
    assert client.session["cart"] == {str(book.pk): {"quantity": 2}}


@pytest.mark.parametrize("quantity", ["0", "-1", "two"])
def test_cart_add_with_wrong_quantity_is_an_error(client, quantity):
    book = BookFactory()

    response = client.post(reverse("cart:add", args=[book.pk]), {"quantity": quantity})

    assert message_levels(response) == ["error"]
    assert not client.session.get("cart")


def test_cart_add_out_of_stock_book_is_an_error(client):
    book = BookFactory(stock=0)

    response = client.post(reverse("cart:add", args=[book.pk]), {"quantity": 1})

    assert message_levels(response) == ["error"]


def test_cart_remove_and_clear(client):
    first, second = BookFactory(), BookFactory()
    for book in (first, second):
        client.post(reverse("cart:add", args=[book.pk]), {"quantity": 1})

    removed = client.post(reverse("cart:remove", args=[first.pk]))
    assert list(client.session["cart"]) == [str(second.pk)]
    assert message_levels(removed)[-1] == "success"

    cleared = client.post(reverse("cart:clear"))
    assertRedirects(cleared, reverse("cart:detail"))
    assert not client.session.get("cart")


# ---------------------------------------------------------------------------
# Orders and payments: access rules
# ---------------------------------------------------------------------------


def test_checkout_needs_login(client):
    url = reverse("orders:checkout")

    assertRedirects(client.get(url), f"{reverse('users:login')}?next={url}")


def test_checkout_with_empty_cart_goes_to_cart(customer_client):
    response = customer_client.get(reverse("orders:checkout"))

    assertRedirects(response, reverse("cart:detail"))


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_checkout_accepts_only_get_and_post(customer_client, method):
    """AI review (AI_REVIEW.md, checkout): other methods got the form with 200."""
    response = getattr(customer_client, method)(reverse("orders:checkout"))

    assert response.status_code == 405


def test_checkout_form_is_prefilled_from_profile(customer, customer_client):
    customer.phone, customer.address = "+380671234567", "Kyiv"
    customer.save()
    customer_client.post(reverse("cart:add", args=[BookFactory().pk]), {"quantity": 1})

    response = customer_client.get(reverse("orders:checkout"))

    assert response.context["form"].initial == {
        "full_name": "Ann Shevchenko",
        "phone": "+380671234567",
        "address": "Kyiv",
    }


def test_someone_elses_order_is_404(customer, other_customer_client):
    order = OrderFactory(user=customer)

    assert other_customer_client.get(order.get_absolute_url()).status_code == 404
    response = other_customer_client.post(reverse("orders:cancel", args=[order.pk]))
    assert response.status_code == 404
    order.refresh_from_db()
    assert order.status == Order.Status.NEW


def test_my_orders_lists_only_own_orders_with_books_count(customer, other_customer, customer_client):
    mine = OrderFactory(user=customer, items=[(BookFactory(), 2), (BookFactory(), 1)])
    OrderFactory(user=other_customer)

    response = customer_client.get(reverse("orders:list"))

    orders = list(response.context["orders"])
    assert orders == [mine]
    assert orders[0].books_count == 3


def test_payment_success_with_someone_elses_session_is_404(customer, other_customer_client, fake_stripe):
    payment = PaymentFactory(order__user=customer)

    response = other_customer_client.get(reverse("payments:success"), {"session_id": payment.external_id})

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Webhook: requests that are refused
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["manual", "paypal"])
def test_webhook_of_provider_without_webhooks_is_404(client, provider):
    response = client.post(reverse("payments:webhook", args=[provider]), data="{}", content_type="application/json")

    assert response.status_code == 404


def test_webhook_with_wrong_signature_is_400(client):
    payload = stripe_event_payload("checkout.session.completed", "cs_test_1")

    response = client.post(
        reverse("payments:webhook", args=["stripe"]),
        data=payload,
        content_type="application/json",
        headers=stripe_webhook_headers(payload, secret="whsec_somebody_else"),
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def test_profile_edit_saves_own_data(customer, customer_client):
    response = customer_client.post(
        reverse("users:profile_edit"),
        {"first_name": "Anna", "last_name": "S", "phone": "+380 67 765 43 21", "address": "Odesa"},
    )

    assertRedirects(response, reverse("users:profile"))
    customer.refresh_from_db()
    assert (customer.first_name, customer.phone, customer.address) == ("Anna", "+380677654321", "Odesa")


def test_logged_in_user_is_sent_away_from_sign_up(customer_client):
    response = customer_client.get(reverse("users:signup"))

    assertRedirects(response, reverse("books:list"))


# ---------------------------------------------------------------------------
# Project-level: /health/ and the timing middleware
# ---------------------------------------------------------------------------


def test_health_ok(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "cache": "ok"}


def test_health_reports_broken_cache_with_503(client, monkeypatch):
    async def broken_cache():  # the checks are async functions now
        raise ConnectionError("Redis is down (test)")

    # CHECKS is a dict: replace one entry for this test only
    monkeypatch.setitem(config_views.CHECKS, "cache", broken_cache)

    response = client.get(reverse("health"))

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "ok", "cache": "error"}


def test_every_response_has_timing_headers(client):
    response = client.get(reverse("books:list"))

    assert response["X-Request-Duration"].endswith("ms")
    assert response["Server-Timing"].startswith("app;dur=")
