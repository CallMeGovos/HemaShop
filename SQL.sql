-- Tạo database (nếu chưa có)
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'HemaShopDB')
BEGIN
    CREATE DATABASE HemaShopDB;
END;
GO

-- Sử dụng database
USE HemaShopDB;
GO
 
-- Tạo bảng types
CREATE TABLE types (
    type_id INT IDENTITY(1,1) PRIMARY KEY,
    type NVARCHAR(50) NOT NULL,
    is_active BIT NOT NULL DEFAULT 1
);
GO

-- Tạo bảng brands
CREATE TABLE brands (
    brand_id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    logo TEXT,
    is_active BIT NOT NULL DEFAULT 1
);
GO

-- Tạo bảng products
CREATE TABLE products (
    product_id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(255) NOT NULL,
    type_id INT NOT NULL,
    brand_id INT NOT NULL,
    price DECIMAL(10, 2),
    url_image_0 TEXT,
    url_image_1 TEXT,
    description TEXT,
    FOREIGN KEY (type_id) REFERENCES types(type_id),
    FOREIGN KEY (brand_id) REFERENCES brands(brand_id)
);
GO

-- Tạo bảng users
CREATE TABLE users (
    user_id INT IDENTITY(1,1) PRIMARY KEY,
    full_name NVARCHAR(50) NOT NULL,
    username VARCHAR(15) NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(50) NULL,
    address NVARCHAR(50) NULL,
    phone VARCHAR(10) NULL,
    birth_date SMALLDATETIME NULL
);
GO

-- Tạo bảng cart
CREATE TABLE cart (
    cart_id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    discount DECIMAL(5, 2) DEFAULT 0.00, -- Giảm giá dưới dạng phần trăm (0-100)
    total_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
GO

-- Tạo bảng discounts
CREATE TABLE discounts (
    discount_id INT IDENTITY(1,1) PRIMARY KEY,
    product_id INT NOT NULL,
    discount DECIMAL(5, 2) NOT NULL, -- Giảm giá dưới dạng phần trăm (0-100)
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
GO

-- Tạo bảng orders
CREATE TABLE orders (
    order_id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL,
    full_name NVARCHAR(50) NOT NULL,
    address NVARCHAR(50) NOT NULL,
    phone VARCHAR(10) NOT NULL,
    email NVARCHAR(50) NOT NULL,
    order_date SMALLDATETIME NOT NULL,
    delivery_date SMALLDATETIME NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    status INT DEFAULT 0
);
GO

CREATE TABLE order_details (
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(10, 2) NOT NULL,
    discount DECIMAL(5, 2) DEFAULT 0.00,
    total_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
GO

-- Tạo bảng admin
CREATE TABLE admin (
    admin_id INT IDENTITY(1,1) PRIMARY KEY,
    account VARCHAR(50) NOT NULL,
    password VARCHAR(255) NOT NULL
);
GO

CREATE TABLE best_sellers (
    best_seller_id INT PRIMARY KEY IDENTITY(1,1),
    product_id INT NOT NULL,
    sales_count INT DEFAULT 0,
    created_at DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
GO

-- Chèn dữ liệu mẫu cho bảng types
INSERT INTO types (type, is_active) VALUES
    ('Long Sword', 1),
    ('Shield', 1),
    ('Armor', 1),
    ('Spear', 1);
GO

-- Chèn dữ liệu mẫu cho bảng brands
INSERT INTO brands (name, logo, is_active) VALUES
    ('Red Dragon', 'red_dragon.png', 1),
    ('SPES', 'spes.png', 1),
    ('Regenyei Armory', 'regenyei_armory.png', 1),
    ('Funtasma', 'funtasma.png', 1),
    ('Targaryen', 'targaryen.png', 1);
GO

-- Chèn dữ liệu mẫu cho bảng products
INSERT INTO products (name, type_id, brand_id, price, url_image_0, url_image_1, description) VALUES
    ('Dark Sister', 1, 5, 250.00, 'dark_sister_0.png', 'dark_sister_1.png', 'A legendary sword with a sharp edge, perfect for combat training.'),
    ('Federschwert', 1, 2, 200.00, 'federschwert_0.png', 'federschwert_1.png', 'A durable training sword designed for safety and performance.'),
    ('Buckler', 2, 3, 80.00, 'buckler_0.png', 'buckler_1.png', 'A small, round shield ideal for historical fencing.'),
    ('Fencing Jacket', 3, 1, 120.00, 'fencing_jacket_0.png', 'fencing_jacket_1.png', 'Protective jacket with high-quality padding for HEMA practice.'),
    ('Spear of Valyria', 4, 5, 150.00, 'spear_valyria_0.png', 'spear_valyria_1.png', 'A lightweight spear with a historical design for training.');
GO


-- Chèn dữ liệu mẫu cho bảng discounts
INSERT INTO discounts (product_id, discount) VALUES
    (1, 10.00),  -- Dark Sister giảm 10%
    (2, 5.00),   -- Federschwert giảm 5%
    (4, 15.00);  -- Fencing Jacket giảm 15%
GO

-- Chèn dữ liệu mẫu cho bảng admin
INSERT INTO admin (account, password) VALUES
    ('a1', 'a1');
GO

CREATE PROCEDURE sp_CreateOrder
    @UserId INT,
    @FullName NVARCHAR(50),
    @Address NVARCHAR(50),
    @Phone VARCHAR(10),
    @Email NVARCHAR(50),
    @OrderDate SMALLDATETIME,
    @DeliveryDate SMALLDATETIME,
    @TotalAmount DECIMAL(10,2)
AS
BEGIN
    SET NOCOUNT ON; -- Ngăn chặn thông báo "rows affected"
    BEGIN TRANSACTION;
    BEGIN TRY
        -- Chèn vào bảng orders
        INSERT INTO orders (user_id, full_name, address, phone, email, order_date, delivery_date, total_amount, status)
        VALUES (@UserId, @FullName, @Address, @Phone, @Email, @OrderDate, @DeliveryDate, @TotalAmount, 0);

        DECLARE @OrderId INT = SCOPE_IDENTITY();

        -- Chèn vào bảng order_details
        INSERT INTO order_details (order_id, product_id, quantity, unit_price, discount, total_price)
        SELECT @OrderId, c.product_id, c.quantity, p.price, c.discount, c.total_price
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id = @UserId;

        -- Xóa giỏ hàng
        DELETE FROM cart WHERE user_id = @UserId;

        COMMIT TRANSACTION;
        SELECT @OrderId AS OrderId; -- Trả về order_id
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
        DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
        DECLARE @ErrorState INT = ERROR_STATE();
        RAISERROR (@ErrorMessage, @ErrorSeverity, @ErrorState); -- Ném lỗi ra cho Python
    END CATCH
END;
GO
