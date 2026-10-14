-- PrintWise database schema (MySQL / MariaDB)
-- Run it with:  flask --app run init-db      (or import this file in phpMyAdmin)
--
-- Keep the style simple: one "id INT UNSIGNED NOT NULL AUTO_INCREMENT" primary key
-- per table, so the same file can also build the in-memory test database.

CREATE TABLE IF NOT EXISTS print_shops (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  address VARCHAR(255) NOT NULL,
  contact_phone VARCHAR(30) NULL,
  contact_email VARCHAR(120) NULL,
  hours VARCHAR(160) NULL,
  description TEXT NULL,
  is_active TINYINT NOT NULL DEFAULT 1,
  accepting_orders TINYINT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS users (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  role VARCHAR(20) NOT NULL DEFAULT 'customer',
  username VARCHAR(30) NOT NULL,
  email VARCHAR(120) NOT NULL,
  full_name VARCHAR(120) NOT NULL,
  phone VARCHAR(30) NULL,
  password_hash VARCHAR(255) NOT NULL,
  avatar_filename VARCHAR(80) NULL,
  shop_id INT UNSIGNED NULL,
  email_verified TINYINT NOT NULL DEFAULT 0,
  is_active TINYINT NOT NULL DEFAULT 1,
  must_change_password TINYINT NOT NULL DEFAULT 0,
  failed_logins INT NOT NULL DEFAULT 0,
  locked_until DATETIME NULL,
  last_login_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE (username),
  UNIQUE (email),
  CONSTRAINT fk_users_shop FOREIGN KEY (shop_id) REFERENCES print_shops (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS services (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  shop_id INT UNSIGNED NOT NULL,
  name VARCHAR(80) NOT NULL,
  description VARCHAR(255) NULL,
  paper_sizes VARCHAR(255) NOT NULL,
  paper_types VARCHAR(255) NOT NULL,
  color_modes VARCHAR(40) NOT NULL DEFAULT 'bw,color',
  is_active TINYINT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_services_shop FOREIGN KEY (shop_id) REFERENCES print_shops (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_no VARCHAR(20) NULL,
  customer_id INT UNSIGNED NOT NULL,
  shop_id INT UNSIGNED NOT NULL,
  service_id INT UNSIGNED NULL,
  service_name VARCHAR(80) NOT NULL,
  paper_size VARCHAR(80) NOT NULL,
  paper_type VARCHAR(80) NOT NULL,
  color_mode VARCHAR(10) NOT NULL,
  sides VARCHAR(10) NOT NULL DEFAULT 'single',
  copies INT NOT NULL DEFAULT 1,
  pages INT NULL,
  notes VARCHAR(500) NULL,
  file_name VARCHAR(255) NOT NULL,
  file_stored VARCHAR(80) NOT NULL,
  file_size INT NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  status_note VARCHAR(255) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  completed_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE (order_no),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES users (id),
  CONSTRAINT fk_orders_shop FOREIGN KEY (shop_id) REFERENCES print_shops (id),
  CONSTRAINT fk_orders_service FOREIGN KEY (service_id) REFERENCES services (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_status_log (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id INT UNSIGNED NOT NULL,
  status VARCHAR(20) NOT NULL,
  note VARCHAR(255) NULL,
  changed_by INT UNSIGNED NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_log_order FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS transactions (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  receipt_no VARCHAR(20) NULL,
  order_id INT UNSIGNED NOT NULL,
  shop_id INT UNSIGNED NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  method VARCHAR(20) NOT NULL DEFAULT 'cash',
  received_by INT UNSIGNED NULL,
  note VARCHAR(255) NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE (receipt_no),
  UNIQUE (order_id),
  CONSTRAINT fk_tx_order FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
  CONSTRAINT fk_tx_shop FOREIGN KEY (shop_id) REFERENCES print_shops (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inventory_items (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  shop_id INT UNSIGNED NOT NULL,
  name VARCHAR(100) NOT NULL,
  category VARCHAR(30) NOT NULL DEFAULT 'paper',
  unit VARCHAR(20) NOT NULL DEFAULT 'sheets',
  quantity INT NOT NULL DEFAULT 0,
  low_stock_level INT NOT NULL DEFAULT 0,
  notes VARCHAR(255) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_inventory_shop FOREIGN KEY (shop_id) REFERENCES print_shops (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inventory_logs (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  item_id INT UNSIGNED NOT NULL,
  change_qty INT NOT NULL,
  quantity_after INT NOT NULL,
  reason VARCHAR(120) NULL,
  changed_by INT UNSIGNED NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_invlog_item FOREIGN KEY (item_id) REFERENCES inventory_items (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notifications (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  title VARCHAR(120) NOT NULL,
  message VARCHAR(255) NOT NULL,
  link VARCHAR(255) NULL,
  is_read TINYINT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
