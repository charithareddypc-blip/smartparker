# Smart Parking Management System (SmartPark Pro)

A modern, full-stack, beginner-friendly **Smart Parking Management System** built with **Python Flask**, **MySQL**, **Bootstrap 5**, and **Chart.js**.

The application manages parking spaces, reservations, simulated payments, live occupancy, and vehicle check-in/check-out with dynamic dashboard analytics, strict concurrency control, and conflict prevention.

---

## Table of Contents
1. [Key Features](#key-features)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Windows Installation & Setup Guide](#windows-installation--setup-guide)
   - [Step 1: Install Python & MySQL](#step-1-install-python--mysql)
   - [Step 2: Clone or Open Project in VS Code](#step-2-clone-or-open-project-in-vs-code)
   - [Step 3: Create & Activate Virtual Environment](#step-3-create--activate-virtual-environment)
   - [Step 4: Install Dependencies](#step-4-install-dependencies)
   - [Step 5: Configure Environment Variables (.env)](#step-5-configure-environment-variables-env)
   - [Step 6: Initialize the Database (MySQL Workbench or CLI)](#step-6-initialize-the-database-mysql-workbench-or-cli)
   - [Step 7: Initialize Administrator Account](#step-7-initialize-administrator-account)
   - [Step 8: Run the Flask Application](#step-8-run-the-flask-application)
5. [Feature Walkthrough & Testing Flows](#feature-walkthrough--testing-flows)
6. [Automated Test Suite](#automated-test-suite)
7. [Troubleshooting Common Issues](#troubleshooting-common-issues)
8. [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)

---

## Key Features

- **Executive Admin Dashboard:**
  - Real-time summary cards: Total Spaces, Available Spaces (green), Reserved Spaces (amber), Occupied Spaces (red), Total Bookings, Payments Collected, and Pending Collections.
  - Calculated **Occupancy Percentage**: `(Occupied Spaces / Total Parking Spaces) * 100`.
  - Dynamic **Chart.js** charts: Occupancy Doughnut breakdown, 7-Day Reservations trend, and Daily Revenue trend.
  - Live Parking Bays overview and recent transactions.

- **Parking Space Management:**
  - Visual parking slot cards with real-time status indicators.
  - Add, edit, and delete slots.
  - **Duplicate prevention:** Prevents duplicate slot numbers within the same floor or area.
  - **Deletion safeguards:** Deletion is strictly prevented if a slot is currently occupied or assigned to an active/reserved booking.

- **Reservation Management:**
  - Time-window booking with start and end datetime pickers.
  - **Strict overlap prevention:** Rejects overlapping reservations on the same slot (`(start_time < existing_end) AND (end_time > existing_start)`).
  - **Real-time fee calculator:** Computes duration and price before confirmation via AJAX (`/api/reservations/estimate`).
  - Safe cancellation releasing slots for upcoming reservations.
  - CSV report export.

- **Simulated Payment Gateway & Billing:**
  - Educational, clearly-labeled simulated payment gateway.
  - Support for Demo Card, Demo UPI, and Cash at entrance desk.
  - **Duplicate payment prevention:** Rejects double charges on paid reservations.
  - Unique transaction reference generator (`TXN-YYYYMMDD-XXXX`).
  - Printable, professional payment receipts with `@media print` layout.
  - CSV export for financial audit trails.

- **Live Facility Occupancy & Gate Operations:**
  - Visual multi-floor slot map.
  - Vehicle **Check-In**: Validates reservation, marks slot occupied, and starts an active session.
  - Vehicle **Check-Out**: Computes actual duration, final billed fee, and releases the slot to available.
  - Real-time audit logs of all check-in/out and cancellation events.

- **Customer & Vehicle Management:**
  - Customer directory with registered vehicle plates and historical booking profiles.

- **Admin Authentication & Security:**
  - Password hashing with PBKDF2/scrypt (`werkzeug.security`).
  - Session protection (`@admin_required` decorator on management routes).
  - Parameterized SQL queries to eliminate SQL injection vulnerabilities.
  - Database transactions with rollback on failure.

---

## Technology Stack

- **Backend:** Python 3.10+ / Flask 3.x
- **Database:** MySQL 8.0+ (with `mysql-connector-python`)
- **Zero-Config Fallback:** Built-in auto-switching SQLite demo mode for instant evaluation if MySQL service is not yet started.
- **Frontend:** HTML5, CSS3, Vanilla JavaScript, Bootstrap 5.3
- **Icons:** Bootstrap Icons 1.11
- **Charts:** Chart.js 4.4
- **Testing:** Pytest

---

## Project Structure

```text
intelligent-parking-management/
├── app.py                      # Flask application entrypoint & factory
├── config.py                   # Configuration & environment loader
├── database.py                 # Resilient database connection layer
├── init_db.py                  # Database initialization & Admin CLI
├── requirements.txt            # Python dependencies
├── .env.example                # Example environment configuration
├── .env                        # Local active environment variables
├── .gitignore                  # Git ignore rules
├── schema.sql                  # MySQL database schema & sample seed data
├── README.md                   # Comprehensive documentation
├── routes/
│   ├── auth.py                 # Admin login, logout, & session guards
│   ├── dashboard.py            # Dashboard metrics & chart API
│   ├── parking.py              # Parking bay CRUD & safeguards
│   ├── reservations.py         # Reservation workflow & CSV export
│   ├── payments.py             # Demo gateway & receipts
│   ├── occupancy.py            # Live occupancy & check-in/checkout
│   └── customers.py            # Customer directory & vehicle records
├── services/
│   ├── reservation_service.py  # Concurrency, overlaps, fee logic
│   ├── payment_service.py      # Transaction & receipt processing
│   └── occupancy_service.py    # Gate operations & audit logging
├── templates/
│   ├── base.html               # Master layout with navy sidebar
│   ├── login.html              # Admin authentication view
│   ├── dashboard.html          # Executive dashboard & Chart.js
│   ├── parking_slots.html      # Visual bay grid & data table
│   ├── reservations.html       # Reservations table & filter toolbar
│   ├── reservation_form.html   # Booking form & live fee calculator
│   ├── reservation_details.html# Single reservation profile
│   ├── payments.html           # Payment transactions & revenue cards
│   ├── payment_process.html    # Simulated payment sandbox
│   ├── receipt.html            # Printable payment receipt
│   ├── occupancy.html          # Live visual slot map & gate check-in
│   ├── customers.html          # Customer directory
│   ├── customer_details.html   # Customer history view
│   └── error.html              # Custom 404 & 500 error pages
├── static/
│   ├── css/
│   │   └── style.css           # Custom design system & print styles
│   ├── js/
│   │   ├── dashboard.js        # Chart.js initialization
│   │   └── parking.js          # Live fee estimation & AJAX
│   └── images/
└── tests/
    ├── conftest.py             # Test fixtures & isolated DB setup
    ├── test_reservations.py    # Overlaps, slots, fee tests
    ├── test_payments.py        # Demo payments, checkin/out tests
    └── test_routes.py          # HTTP 200 endpoint assertions
```

---

## Windows Installation & Setup Guide

### Step 1: Install Python & MySQL
1. **Python 3.10+**: Download from [python.org](https://www.python.org/downloads/). Ensure you check the box **"Add Python to PATH"** during installation.
2. **MySQL Server & Workbench**:
   - Download the **MySQL Community Installer** from [dev.mysql.com](https://dev.mysql.com/downloads/installer/).
   - Alternatively, install **XAMPP** or **WampServer** to get MySQL running on port 3306.

### Step 2: Open Project in Visual Studio Code
1. Open PowerShell or Terminal.
2. Navigate to your project folder:
   ```powershell
   cd "c:\Users\haswa\Downloads\intelligent parking mangement"
   ```
3. Open in VS Code:
   ```powershell
   code .
   ```

### Step 3: Create & Activate Virtual Environment
In your VS Code terminal (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
*(If PowerShell displays an Execution Policy warning, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and re-run the activate command).*

### Step 4: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables (.env)
A `.env` file has been provided. If needed, copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```
Open `.env` and verify your MySQL credentials:
```ini
SECRET_KEY=smart-parking-secret-key-39185a720df545b6
FLASK_ENV=development
FLASK_DEBUG=1
PORT=5000

# MySQL Database Settings
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=smart_parking_db

TIMEZONE=Asia/Kolkata
```

### Step 6: Initialize the Database (MySQL Workbench or CLI)

#### Method A: Using MySQL Workbench (GUI)
1. Open **MySQL Workbench** and connect to your local MySQL instance.
2. Click **File -> Open SQL Script...** and select `schema.sql` from the project directory.
3. Click the **Execute (Lightning icon)** to run the entire script.
4. Refresh your Schemas panel in Workbench; you will see `smart_parking_db` with all 9 tables and sample test data ready.

#### Method B: Using the Python CLI
You can initialize the schema automatically via the included CLI tool:
```powershell
python init_db.py --mode mysql
```
*(Note: If MySQL server is not currently running on your system, the application will automatically run in local zero-config mode so you can test immediately without interruption).*

### Step 7: Initialize Administrator Account
A default administrator account is pre-configured:
- **Username:** `admin`
- **Password:** `Admin@123`

To securely create a custom administrator or reset password:
```powershell
python init_db.py --create-admin --username myadmin --password MySecurePassword123 --email admin@domain.com --name "Head Admin"
```

### Step 8: Run the Flask Application
Start the Flask development server:
```powershell
python app.py
```
Output:
```text
============================================================
  SMART PARKING MANAGEMENT SYSTEM
  Starting Development Server on http://127.0.0.1:5000
  Admin Login: http://127.0.0.1:5000/login
  Default Credentials: admin / Admin@123
============================================================
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## Feature Walkthrough & Testing Flows

1. **Sign In:**
   - Go to `http://127.0.0.1:5000/login`.
   - Enter `admin` / `Admin@123`.

2. **Explore Dashboard (`/dashboard`):**
   - Check the 8 live metric cards.
   - Inspect the interactive Chart.js doughnut chart, 7-day bookings bar chart, and revenue trend chart.

3. **Manage Parking Slots (`/parking`):**
   - Switch between **Visual Slot Grid** and **Data Table**.
   - Filter by floor (Ground, 1st Floor, Basement) or slot type (EV, Accessible, Regular, Compact).
   - Click **Add New Slot**: Add `G-08` in `AREA-G`. Try creating `G-08` again to verify duplicate rejection.
   - Try deleting an occupied slot (e.g. `G-02`) to verify deletion protection.

4. **Create a Reservation (`/reservations/new`):**
   - Select a parking slot.
   - Choose start and end dates/times.
   - Watch the **Live Price Estimator** calculate hours and fee in real-time.
   - Enter customer name and vehicle license plate.
   - Click **Confirm Reservation**.

5. **Process a Demo Payment (`/payments`):**
   - The booking automatically redirects to the Simulated Payment Gateway.
   - Select payment method (Demo Card, Demo UPI, or Cash Desk).
   - Test either "Simulate Successful Payment" or "Simulate Payment Failure".
   - View the generated transaction reference (`TXN-...`).
   - Click **Print Receipt / Save PDF** to view the clean printable layout.

6. **Check-In & Check-Out (`/occupancy`):**
   - Go to **Live Occupancy**.
   - Click **Check In Vehicle**: Select an eligible reservation code.
   - Observe the slot card color turn from Amber (Reserved) to **Red (Occupied)** and the Active Sessions count increment.
   - Under Active Parking Sessions, click **Check-Out**: The system computes actual parked time and releases the slot back to **Green (Available)**.

---

## Automated Test Suite

The project includes unit and integration tests covering business rules, concurrency safeguards, payment prevention, and route protection.

To run tests:
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Expected output:
```text
tests/test_payments.py::test_demo_payment_success PASSED
tests/test_payments.py::test_duplicate_payment_prevention PASSED
tests/test_payments.py::test_demo_payment_failure_simulation PASSED
tests/test_payments.py::test_revenue_summary_counts_only_paid PASSED
tests/test_payments.py::test_vehicle_checkin_and_checkout PASSED
tests/test_payments.py::test_admin_route_protection PASSED
tests/test_reservations.py::test_fee_calculation PASSED
tests/test_reservations.py::test_invalid_times_rejection PASSED
tests/test_reservations.py::test_successful_reservation_creation PASSED
tests/test_reservations.py::test_overlapping_reservation_rejection PASSED
tests/test_reservations.py::test_reservation_cancellation PASSED
tests/test_reservations.py::test_slot_creation_and_duplicate_prevention PASSED
tests/test_reservations.py::test_delete_occupied_slot_protection PASSED
tests/test_routes.py::test_all_pages_render PASSED

14 passed in 0.59s
```

---

## Troubleshooting Common Issues

1. **"Access denied for user 'root'@'localhost'"**
   - Check your MySQL password in `.env`.
   - If using XAMPP, default user is `root` with an empty password (`DB_PASSWORD=`).
   - If using MySQL Installer with a root password, set `DB_PASSWORD=your_password`.

2. **"Can't connect to MySQL server on '127.0.0.1:3306'"**
   - Open Windows Services (`services.msc`) and ensure `MySQL80` (or `MySQL`) service is running.
   - If using XAMPP, click **Start** next to MySQL in the XAMPP Control Panel.
   - Notice: The app has an automatic fallback to local zero-config mode, indicated on the dashboard topbar badge.

3. **PowerShell Script Execution Restriction:**
   - If `Activate.ps1` gives a script policy error:
     ```powershell
     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
     .\.venv\Scripts\Activate.ps1
     ```

4. **Port 5000 Already in Use:**
   - Change `PORT=5001` in your `.env` file and restart `python app.py`.

---

## Known Limitations & Future Roadmap

- **Hardware IoT Sensors:** Physical ultrasonic or camera sensors (ANPR/LPR) are not physically connected in this version; check-ins and check-outs are managed via administrative operator actions.
- **Production Payment Gateways:** Payments are currently handled through the documented simulation gateway; webhook endpoints for Stripe or Razorpay can be mapped directly into `PaymentService`.
- **Future Enhancements:**
  - Automated license plate recognition (ALPR) camera integration.
  - Multi-tenant role permissions (e.g. Attendant vs Super Admin).
  - Customer self-service booking portal with SMS/WhatsApp notifications.
