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

-- Tạo bảng orer_details
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

-- Tạo bảng best_sellers
CREATE TABLE best_sellers (
    best_seller_id INT PRIMARY KEY IDENTITY(1,1),
    product_id INT NOT NULL,
    sales_count INT DEFAULT 0,
    created_at DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
GO

-- Tạo bảng warehouse
CREATE TABLE warehouse (
    warehouse_id NVARCHAR(50) PRIMARY KEY,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    import_unit_price DECIMAL(10, 2),
    location NVARCHAR(255),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
)

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
