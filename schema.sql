-- Smart Parking Management System - Database Schema
-- Compatible with MySQL 8.0+
-- Database: smart_parking_db

CREATE DATABASE IF NOT EXISTS smart_parking_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_parking_db;

-- 1. Admins Table
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. Customers Table
CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_customer_phone (phone),
    INDEX idx_customer_email (email)
) ENGINE=InnoDB;

-- 3. Vehicles Table
CREATE TABLE IF NOT EXISTS vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    license_plate VARCHAR(20) NOT NULL UNIQUE,
    vehicle_type VARCHAR(30) DEFAULT 'Sedan',
    make_model VARCHAR(60),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    INDEX idx_vehicle_plate (license_plate)
) ENGINE=InnoDB;

-- 4. Parking Areas Table
CREATE TABLE IF NOT EXISTS parking_areas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    area_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    floor_level VARCHAR(30) NOT NULL,
    total_slots INT DEFAULT 0,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 5. Parking Slots Table
CREATE TABLE IF NOT EXISTS parking_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    area_id INT NOT NULL,
    slot_number VARCHAR(20) NOT NULL,
    slot_type ENUM('regular', 'compact', 'accessible', 'ev') NOT NULL DEFAULT 'regular',
    hourly_rate DECIMAL(10, 2) NOT NULL DEFAULT 5.00,
    status ENUM('available', 'reserved', 'occupied', 'maintenance') NOT NULL DEFAULT 'available',
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (area_id) REFERENCES parking_areas(id) ON DELETE RESTRICT,
    UNIQUE KEY uq_area_slot (area_id, slot_number),
    INDEX idx_slot_status (status),
    INDEX idx_slot_type (slot_type)
) ENGINE=InnoDB;

-- 6. Reservations Table
CREATE TABLE IF NOT EXISTS reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reservation_code VARCHAR(30) NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    vehicle_id INT NOT NULL,
    slot_id INT NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    duration_hours DECIMAL(6, 2) NOT NULL,
    estimated_amount DECIMAL(10, 2) NOT NULL,
    actual_amount DECIMAL(10, 2) DEFAULT NULL,
    booking_status ENUM('pending', 'reserved', 'active', 'completed', 'cancelled') NOT NULL DEFAULT 'reserved',
    payment_status ENUM('pending', 'paid', 'refunded') NOT NULL DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT,
    FOREIGN KEY (slot_id) REFERENCES parking_slots(id) ON DELETE RESTRICT,
    INDEX idx_slot_times (slot_id, start_time, end_time),
    INDEX idx_booking_status (booking_status),
    INDEX idx_payment_status (payment_status)
) ENGINE=InnoDB;

-- 7. Payments Table
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reservation_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL DEFAULT 'demo_gateway',
    transaction_ref VARCHAR(100) NOT NULL UNIQUE,
    payment_status ENUM('pending', 'paid', 'failed', 'refunded') NOT NULL DEFAULT 'pending',
    notes TEXT,
    paid_at DATETIME DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE CASCADE,
    INDEX idx_payment_status (payment_status),
    INDEX idx_transaction_ref (transaction_ref)
) ENGINE=InnoDB;

-- 8. Parking Sessions Table (Check-in / Check-out tracking)
CREATE TABLE IF NOT EXISTS parking_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reservation_id INT DEFAULT NULL,
    slot_id INT NOT NULL,
    vehicle_id INT NOT NULL,
    check_in_time DATETIME NOT NULL,
    check_out_time DATETIME DEFAULT NULL,
    actual_duration_hours DECIMAL(6, 2) DEFAULT NULL,
    initial_fee DECIMAL(10, 2) NOT NULL,
    final_fee DECIMAL(10, 2) DEFAULT NULL,
    status ENUM('active', 'completed') NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE SET NULL,
    FOREIGN KEY (slot_id) REFERENCES parking_slots(id) ON DELETE RESTRICT,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT,
    INDEX idx_session_status (status)
) ENGINE=InnoDB;

-- 9. Occupancy Logs Table
CREATE TABLE IF NOT EXISTS occupancy_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slot_id INT NOT NULL,
    event_type ENUM('check_in', 'check_out', 'reservation_hold', 'cancellation', 'status_change') NOT NULL,
    details VARCHAR(255) NOT NULL,
    logged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (slot_id) REFERENCES parking_slots(id) ON DELETE CASCADE,
    INDEX idx_log_slot (slot_id),
    INDEX idx_log_time (logged_at)
) ENGINE=InnoDB;

-- ========================================================
-- Sample Initial Data for Testing & Demonstration
-- ========================================================

-- Initial Administrator
-- Username: admin
-- Password: Admin@123 (hashed using scrypt/pbkdf2 compatible with Werkzeug)
INSERT INTO admins (username, email, password_hash, full_name)
VALUES ('admin', 'admin@smartparking.local', 'scrypt:32768:8:1$yLgX7n2K8M$93f9efdd8829be7bc2b95c8793b8fbd46399a9b60dafb6047da0344405391d1ea173beae20485a0cbb029ae4ea1ec1cb14b09b52a1d2f09d3b14643717243916', 'System Administrator')
ON DUPLICATE KEY UPDATE id=id;

-- Parking Areas
INSERT INTO parking_areas (area_code, name, floor_level, total_slots, description) VALUES
('AREA-G', 'Ground Level North Wing', 'Ground Floor', 6, 'Convenient ground-level parking with EV charging and quick exit'),
('AREA-F1', 'Level 1 South Wing', '1st Floor', 6, 'Standard covered bays with wide access lanes'),
('AREA-B1', 'Basement Executive Bay', 'Basement 1', 6, 'Climate-controlled basement parking with priority accessible spaces')
ON DUPLICATE KEY UPDATE area_code=area_code;

-- Parking Slots
INSERT INTO parking_slots (area_id, slot_number, slot_type, hourly_rate, status) VALUES
(1, 'G-01', 'ev', 8.00, 'available'),
(1, 'G-02', 'ev', 8.00, 'occupied'),
(1, 'G-03', 'accessible', 5.00, 'available'),
(1, 'G-04', 'accessible', 5.00, 'reserved'),
(1, 'G-05', 'regular', 6.00, 'available'),
(1, 'G-06', 'compact', 4.50, 'available'),
(2, 'F1-01', 'regular', 5.00, 'occupied'),
(2, 'F1-02', 'regular', 5.00, 'available'),
(2, 'F1-03', 'regular', 5.00, 'available'),
(2, 'F1-04', 'compact', 4.00, 'available'),
(2, 'F1-05', 'compact', 4.00, 'reserved'),
(2, 'F1-06', 'regular', 5.00, 'available'),
(3, 'B1-01', 'accessible', 6.00, 'available'),
(3, 'B1-02', 'regular', 6.50, 'available'),
(3, 'B1-03', 'regular', 6.50, 'occupied'),
(3, 'B1-04', 'ev', 9.00, 'available'),
(3, 'B1-05', 'regular', 6.50, 'available'),
(3, 'B1-06', 'compact', 5.00, 'available')
ON DUPLICATE KEY UPDATE slot_number=slot_number;

-- Customers
INSERT INTO customers (full_name, email, phone) VALUES
('Alexander Wright', 'alex.wright@example.com', '+1-555-0192'),
('Sophia Martinez', 'sophia.m@example.com', '+1-555-0143'),
('David Chen', 'david.chen@example.com', '+1-555-0188'),
('Emma Watson', 'emma.w@example.com', '+1-555-0164'),
('Marcus Johnson', 'marcus.j@example.com', '+1-555-0177')
ON DUPLICATE KEY UPDATE full_name=full_name;

-- Vehicles
INSERT INTO vehicles (customer_id, license_plate, vehicle_type, make_model) VALUES
(1, 'NYC-8921', 'EV', 'Tesla Model 3'),
(2, 'CA-4298', 'Sedan', 'Toyota Camry'),
(3, 'TX-1044', 'SUV', 'Honda CR-V'),
(4, 'FL-6733', 'Compact', 'Mini Cooper'),
(5, 'WA-5512', 'SUV', 'Ford Explorer')
ON DUPLICATE KEY UPDATE license_plate=license_plate;

-- Sample Active and Historical Reservations
INSERT INTO reservations (reservation_code, customer_id, vehicle_id, slot_id, start_time, end_time, duration_hours, estimated_amount, actual_amount, booking_status, payment_status, notes) VALUES
('RES-2026-1001', 1, 1, 2, '2026-10-15 08:00:00', '2026-10-15 12:00:00', 4.0, 32.00, 32.00, 'active', 'paid', 'Checked in at 08:05 AM'),
('RES-2026-1002', 2, 2, 4, '2026-10-15 10:00:00', '2026-10-15 14:00:00', 4.0, 20.00, NULL, 'reserved', 'paid', 'Upcoming reservation, confirmed'),
('RES-2026-1003', 3, 3, 7, '2026-10-15 07:30:00', '2026-10-15 11:30:00', 4.0, 20.00, 20.00, 'active', 'paid', 'Early morning commuter check-in'),
('RES-2026-1004', 4, 4, 11, '2026-10-15 11:00:00', '2026-10-15 15:00:00', 4.0, 16.00, NULL, 'reserved', 'pending', 'Awaiting payment confirmation'),
('RES-2026-1005', 5, 5, 15, '2026-10-15 09:00:00', '2026-10-15 13:00:00', 4.0, 26.00, 26.00, 'active', 'paid', 'Executive meeting parking')
ON DUPLICATE KEY UPDATE reservation_code=reservation_code;

-- Sample Payments
INSERT INTO payments (reservation_id, amount, payment_method, transaction_ref, payment_status, notes, paid_at) VALUES
(1, 32.00, 'demo_card', 'TXN-20261015-8911', 'paid', 'Simulated Visa Card Payment', '2026-10-15 08:02:11'),
(2, 20.00, 'demo_upi', 'TXN-20261015-4420', 'paid', 'Simulated UPI QuickPay', '2026-10-15 09:12:45'),
(3, 20.00, 'demo_card', 'TXN-20261015-9932', 'paid', 'Simulated MasterCard Payment', '2026-10-15 07:28:19'),
(5, 26.00, 'demo_cash', 'TXN-20261015-1105', 'paid', 'Cash collected at entrance desk', '2026-10-15 09:01:05')
ON DUPLICATE KEY UPDATE transaction_ref=transaction_ref;

-- Active Parking Sessions (For occupied slots)
INSERT INTO parking_sessions (reservation_id, slot_id, vehicle_id, check_in_time, initial_fee, status, notes) VALUES
(1, 2, 1, '2026-10-15 08:05:00', 32.00, 'active', 'Checked in at North EV Gate'),
(3, 7, 3, '2026-10-15 07:31:00', 20.00, 'active', 'Checked in at Level 1 Boom Barrier'),
(5, 15, 5, '2026-10-15 09:02:00', 26.00, 'active', 'Executive basement bay check-in')
ON DUPLICATE KEY UPDATE id=id;

-- Occupancy Logs
INSERT INTO occupancy_logs (slot_id, event_type, details, logged_at) VALUES
(2, 'check_in', 'Vehicle NYC-8921 checked into Slot G-02', '2026-10-15 08:05:00'),
(4, 'reservation_hold', 'Reservation RES-2026-1002 placed on Slot G-04', '2026-10-15 09:12:00'),
(7, 'check_in', 'Vehicle TX-1044 checked into Slot F1-01', '2026-10-15 07:31:00'),
(11, 'reservation_hold', 'Reservation RES-2026-1004 placed on Slot F1-05', '2026-10-15 09:30:00'),
(15, 'check_in', 'Vehicle WA-5512 checked into Slot B1-03', '2026-10-15 09:02:00');
