CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL,
    price      REAL NOT NULL CHECK (price > 0)
);
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    signup_date TEXT NOT NULL,
    channel     TEXT NOT NULL
);
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers,
    order_date  TEXT NOT NULL
);
CREATE TABLE order_items (
    item_id    INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders,
    product_id INTEGER NOT NULL REFERENCES products,
    qty        INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    returned   INTEGER NOT NULL DEFAULT 0 CHECK (returned IN (0, 1))
);
CREATE TABLE ad_spend (
    month   TEXT NOT NULL,   -- YYYY-MM
    channel TEXT NOT NULL,
    spend   REAL NOT NULL,
    PRIMARY KEY (month, channel)
);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_items_order ON order_items(order_id);
