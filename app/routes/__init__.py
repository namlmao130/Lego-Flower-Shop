"""Feature route registration without changing existing url_for endpoints."""


def register_routes(app):
    from . import (
        admin,
        admin_categories,
        admin_chat,
        admin_orders,
        admin_products,
        auth,
        cart,
        chat,
        checkout,
        customer,
        health,
        orders,
        products,
    )

    # Preserve registration order and endpoint names used in existing templates.
    for module in (
        health,
        products,
        auth,
        customer,
        cart,
        checkout,
        orders,
        admin,
        admin_products,
        admin_categories,
        admin_orders,
        chat,
        admin_chat,
    ):
        module.register_routes(app)
